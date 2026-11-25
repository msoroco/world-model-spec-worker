import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from live_entrypoint import camera_builder, transform, verify_site_sources
from runner import check


class FakeBlueprint:
    def __init__(self):
        self.attrs = {}

    def set_attribute(self, name, value):
        self.attrs[name] = value


class FakeSensor:
    def __init__(self, ident):
        self.id = ident
        self.stopped = False
        self.destroyed = False

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.spawned = []

    def get_blueprint_library(self):
        return self

    def find(self, name):
        if name != "sensor.camera.rgb":
            raise ValueError(name)
        return FakeBlueprint()

    def spawn_actor(self, bp, pose, *, attach_to):
        if self.fail_at == len(self.spawned):
            raise ValueError("simulated camera spawn failure")
        sensor = FakeSensor(len(self.spawned) + 1)
        self.spawned.append((bp.attrs.copy(), pose, attach_to, sensor))
        return sensor


class FakeCarla:
    Location = staticmethod(lambda *coords: ("position", coords))
    Rotation = staticmethod(lambda *coords: ("rotation", coords))
    Transform = staticmethod(lambda loc, rot: (loc, rot))


class FakeMap:
    name = "reviewed-map"

    def to_opendrive(self):
        return "source-OpenDRIVE-map"


def source_site():
    cameras = {}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        cameras[name] = {"attachment": "ego" if name == "driver_reference" else "world",
                         "fov_deg": 85, "transform": dict(x=1, y=2, z=3, pitch=0,
                                                       yaw=20, roll=0)}
    return {"cameras": cameras}


class LiveAdapterTest(unittest.TestCase):
    def reviewed_site_fixture(self, root):
        root = Path(root)
        route = dict(ego_route=[{"x": 1}], other_route=[{"x": 2}],
                     ego_spawn={"x": 1}, other_spawn={"x": 2},
                     other_start_tick=0, cameras=source_site()["cameras"])
        district = {"frontage_sources": ["original frontage survey"],
                    "building_use_sources": ["original building-use survey"],
                    "statutory_classification": "unresolved_review"}
        boundary = {"polygon_xy_m": [[0, 0], [1, 0], [0, 1]]}
        payloads = {"map": "source-OpenDRIVE-map",
                    "routes": json.dumps(route), "district": json.dumps(district),
                    "boundary": json.dumps(boundary)}
        site = {**route, "map_name": "reviewed-map",
                "intersection_boundary": dict(boundary), "source_documents": {}}
        keys = {"map": "map_sha256", "routes": "route_sha256",
                "district": "district_source_sha256",
                "boundary": "intersection_boundary_source_sha256"}
        for name, payload in payloads.items():
            path = root / (name + (".xodr" if name == "map" else ".json"))
            path.write_text(payload)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            site[keys[name]] = digest
            site["source_documents"][name] = {"path": path.name, "sha256": digest}
        site["intersection_boundary"]["source_sha256"] = site["intersection_boundary_source_sha256"]
        path = root / "site.json"
        path.write_text(json.dumps(site))
        return path, site

    def test_exact_config_is_executable(self):
        self.assertTrue(check(ROOT).endswith("__intersection_vehicle_near"))

    def test_transforms_require_all_finite_coordinates(self):
        pose = dict(x=1, y=2, z=3, pitch=4, yaw=5, roll=6)
        self.assertEqual(transform(FakeCarla, pose)[0][1], (1., 2., 3.))
        del pose["z"]
        with self.assertRaisesRegex(ValueError, "z must be numeric"):
            transform(FakeCarla, pose)
        pose["z"] = float("nan")
        with self.assertRaisesRegex(ValueError, "z must be finite"):
            transform(FakeCarla, pose)

    def test_four_source_camera_poses_and_dimensions(self):
        world = FakeWorld()
        actors = {"ego": object()}
        sensors = camera_builder(FakeCarla, world, actors, source_site())
        self.assertEqual(len(sensors), 4)
        self.assertEqual(world.spawned[0][0]["image_size_x"], "1920")
        self.assertEqual(world.spawned[1][0]["image_size_x"], "1280")
        self.assertEqual(world.spawned[0][0]["sensor_tick"], "0.05")
        self.assertIsNone(world.spawned[0][2])
        self.assertIs(world.spawned[-1][2], actors["ego"])

    def test_camera_partial_failure_destroys_owned_sensors(self):
        world = FakeWorld(fail_at=2)
        with self.assertRaisesRegex(ValueError, "simulated camera spawn failure"):
            camera_builder(FakeCarla, world, {"ego": object()}, source_site())
        self.assertTrue(all(row[3].stopped and row[3].destroyed for row in world.spawned))

    def test_missing_camera_source_rejected_before_spawn(self):
        site = source_site()
        del site["cameras"]["approach"]
        world = FakeWorld()
        with self.assertRaisesRegex(ValueError, "four reviewed camera poses"):
            camera_builder(FakeCarla, world, {"ego": object()}, site)
        self.assertFalse(world.spawned)

    def test_runner_rejects_changed_case_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            config = json.loads((ROOT / "config.json").read_text())
            config["supported_case_ids"].pop()
            (Path(temp) / "config.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "case selection"):
                check(temp)

    def test_source_documents_bind_live_map_routes_and_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            path, site = self.reviewed_site_fixture(temp)
            self.assertEqual(set(verify_site_sources(path, site, FakeMap())),
                             {"map", "routes", "district", "boundary"})
            site["ego_route"] = [{"x": 99}]
            with self.assertRaisesRegex(ValueError, "route or camera source differs"):
                verify_site_sources(path, site, FakeMap())

    def test_missing_or_stale_document_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path, site = self.reviewed_site_fixture(temp)
            (Path(temp) / "district.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "source hash differs: district"):
                verify_site_sources(path, site, FakeMap())
            site["source_documents"]["district"]["path"] = "../other.json"
            with self.assertRaisesRegex(ValueError, "escapes site directory"):
                verify_site_sources(path, site, FakeMap())

    def test_live_map_hash_must_match_reviewed_xodr(self):
        with tempfile.TemporaryDirectory() as temp:
            path, site = self.reviewed_site_fixture(temp)
            wrong_map = FakeMap()
            wrong_map.to_opendrive = lambda: "changed map"
            with self.assertRaisesRegex(ValueError, "live OpenDRIVE map differs"):
                verify_site_sources(path, site, wrong_map)


if __name__ == "__main__":
    unittest.main()
