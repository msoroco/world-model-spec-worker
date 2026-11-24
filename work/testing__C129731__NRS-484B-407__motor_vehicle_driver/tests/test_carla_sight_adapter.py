import hashlib
import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from carla_sight_adapter import CarlaSightAdapter, capture_original_carla, load_reviewed_site
from native_sight_capture import capture
from sight_measurement import ASSIGNMENT, DIRECTIONS, STATIONS_M


class FakeCameras:
    def __init__(self, world, site, output, carla):
        self.output = output
        self.frames = []

    def append(self, frame):
        self.frames.append(frame)

    def close(self):
        pass

    def files(self):
        if self.frames != list(range(1, 901)):
            raise ValueError("camera frame mismatch")
        files = {}
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            path = self.output / (name + ".mkv")
            path.write_bytes(name.encode())
            files[name] = path
        return files


def loc(x, y, z):
    return Obj(x=x, y=y, z=z)


class Actor:
    def __init__(self, actor_id, x):
        self.id = actor_id
        self.type_id = "vehicle.test"
        self.x = x
        self.frame = 0
        self.controls = []
        self.bounding_box = Obj(get_world_vertices=lambda transform: [
            loc(self.x, float(i % 2), 1.0) for i in range(8)])

    def get_transform(self):
        yaw = 0.0 if self.frame <= 400 else min((self.frame - 400) * 179.0 / 80, 179.0)
        return Obj(location=loc(self.x, 0.0, 0.0),
                   rotation=Obj(yaw=yaw))

    def get_velocity(self):
        return Obj(length=lambda: 0.0)

    def apply_control(self, control):
        self.controls.append(control)


class World:
    def __init__(self, ego):
        self.frame = 0
        self.ego_actor = ego
        self.block = False

    def get_map(self):
        return Obj(to_opendrive=lambda: "reviewed mountain OpenDRIVE",
                   get_waypoint=lambda location, project_to_road=False: Obj(
                       road_id=17, lane_id=-1,
                       transform=Obj(location=location)))

    def get_settings(self):
        return Obj(synchronous_mode=True, fixed_delta_seconds=0.05)

    def tick(self):
        self.frame += 1
        self.ego_actor.frame = self.frame
        return self.frame

    def get_snapshot(self):
        return Obj(frame=self.frame,
                   timestamp=Obj(elapsed_seconds=(self.frame - 1) / 20))

    def cast_ray(self, start, end):
        if not self.block:
            return []
        half = loc((start.x + end.x) / 2, (start.y + end.y) / 2,
                   (start.z + end.z) / 2)
        return [Obj(location=half, label="NativeTerrain")]


def site():
    exact = ASSIGNMENT + "__distance_at_500ft"
    route = {"target_speed_mps": 4.0, "waypoints": [
        {"x": float(x), "y": 0.0, "z": 0.0,
         "road_id": 17, "lane_id": -1} for x in (0, 10, 20)]}
    return {
        "map_source_sha256": hashlib.sha256(b"reviewed mountain OpenDRIVE").hexdigest(),
        "ego_vehicle_id": "1", "approach_vehicle_id": "2",
        "highway_source": "reviewed OpenDRIVE road 17 lane -1",
        "location_kind": "curve",
        "terrain_hit_labels": ["NativeTerrain"],
        "subject_body_hit_labels": ["NativeVehicle"],
        "case_setups": {exact: {"ego_route": route,
                                "approach_route": route}},
        "observer_stations": [
            {"direction": direction, "station_distance_m": distance,
             "location": {"x": 200.0, "y": 1.0 if direction == DIRECTIONS[0] else -1.0,
                          "z": 0.0},
             "road_id": 17, "lane_id": -1,
             "road_waypoint_source": f"reviewed road 17/{direction}/{distance}"}
            for direction in DIRECTIONS for distance in STATIONS_M
        ],
    }


class CarlaSightAdapterTests(unittest.TestCase):
    def setUp(self):
        self.ego = Actor(1, 0.0)
        self.approach = Actor(2, 152.4)
        self.world = World(self.ego)

    def adapter(self, reviewed=None):
        return CarlaSightAdapter(self.world, self.ego, self.approach,
                                 site() if reviewed is None else reviewed, loc,
                                 lambda frame, actor: 400 <= frame <= 480)

    def test_original_native_capture_join_and_ray_hits(self):
        self.world.block = True
        with tempfile.TemporaryDirectory() as tmp:
            result = capture(self.adapter(), ASSIGNMENT + "__distance_at_500ft",
                             Path(tmp) / "attempt")
            self.assertEqual(result["original_frames"], 900)
            self.assertEqual(result["rays_checked"], 810)
            self.assertEqual(result["blocked_ray_counts"],
                             {direction: 405 for direction in DIRECTIONS})
            inventory = json.loads((Path(tmp) / "attempt" / "inventory.json").read_text())
            self.assertEqual(set(inventory["sources"]),
                             {"road_geometry", "frame_map", "ego_motion", "sight_rays"})

    def test_wrong_map_and_actor_identity_rejected_before_tick(self):
        bad = site()
        bad["map_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "loaded OpenDRIVE"):
            self.adapter(bad)
        bad = site()
        bad["approach_vehicle_id"] = "another"
        with self.assertRaisesRegex(ValueError, "actor identity"):
            self.adapter(bad)
        self.assertEqual(self.world.frame, 0)

    def test_new_actor_blueprints_bind_before_dynamic_ids_exist(self):
        reviewed = site()
        reviewed.pop("ego_vehicle_id")
        reviewed.pop("approach_vehicle_id")
        reviewed["ego_blueprint_id"] = "vehicle.test"
        reviewed["approach_blueprint_id"] = "vehicle.test"
        self.assertEqual(self.adapter(reviewed).geometry()["ego_vehicle_id"], "1")
        reviewed["approach_blueprint_id"] = "vehicle.other"
        with self.assertRaisesRegex(ValueError, "blueprint differs"):
            self.adapter(reviewed)

    def test_missing_route_station_and_unsourced_turn_rejected(self):
        bad = site()
        bad["observer_stations"].pop()
        with self.assertRaisesRegex(ValueError, "both directions"):
            self.adapter(bad)
        adapter = CarlaSightAdapter(self.world, self.ego, self.approach,
                                    site(), loc, lambda frame, actor: "yes")
        with self.assertRaisesRegex(ValueError, "boolean"):
            adapter.ego({"frame": 1})

    def test_unreviewed_occluder_rejected(self):
        adapter = self.adapter()
        self.world.block = True
        self.world.cast_ray = lambda start, end: [Obj(location=loc(5.0, 0.0, 0.0),
                                                       label="UnreviewedVehicle")]
        with self.assertRaisesRegex(ValueError, "outside reviewed terrain"):
            adapter.ray({"frame": 1, "time_s": 0.0}, DIRECTIONS[0], STATIONS_M[0])

    def test_subject_body_hit_is_visible_not_terrain_occlusion(self):
        adapter = self.adapter()
        self.world.cast_ray = lambda start, end: [Obj(location=loc(0.1, 0.0, 1.0),
                                                       label="NativeVehicle")]
        row = adapter.ray({"frame": 1, "time_s": 0.0}, DIRECTIONS[0], STATIONS_M[0])
        self.assertEqual(row["body_point_clear"], [True] * 9)
        self.assertIsNone(row["terrain_hit_id"])

    def test_station_wrong_loaded_lane_rejected(self):
        reviewed = site()
        reviewed["observer_stations"][0]["lane_id"] = 4
        with self.assertRaisesRegex(ValueError, "differs from loaded road lane"):
            self.adapter(reviewed)

    def test_asynchronous_world_rejected_before_capture(self):
        self.world.get_settings = lambda: Obj(synchronous_mode=False,
                                              fixed_delta_seconds=0.05)
        with self.assertRaisesRegex(ValueError, "synchronous 20 Hz"):
            self.adapter()

    def test_reviewed_site_bytes_are_hash_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "site.json"
            path.write_text(json.dumps(site()) + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            adapter = CarlaSightAdapter.from_reviewed_source(
                self.world, self.ego, self.approach, path, digest, loc,
                lambda frame, actor: 400 <= frame <= 480)
            self.assertEqual(adapter.geometry()["map_source_sha256"],
                             site()["map_source_sha256"])
            path.write_text(json.dumps(dict(site(), location_kind="near_crest")) + "\n")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                load_reviewed_site(path, digest)

    def test_one_call_original_capture_uses_observed_heading(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as tmp:
            root = Path(tmp)
            path = root / "site.json"
            path.write_text(json.dumps(site()) + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = capture_original_carla(
                self.world, self.ego, self.approach, path, digest, loc,
                ASSIGNMENT + "__distance_at_500ft", root / "attempt",
                camera_factory=FakeCameras)
            self.assertGreater(result["turn_frames"], 60)
            self.assertGreater(result["measured_heading_change_deg"], 150)
            self.assertTrue((root / "attempt" / "inventory.json").is_file())

    def test_one_call_capture_applies_both_reviewed_routes_before_ticks(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as tmp:
            root = Path(tmp)
            path = root / "site.json"
            path.write_text(json.dumps(site()) + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            capture_original_carla(
                self.world, self.ego, self.approach, path, digest, loc,
                ASSIGNMENT + "__distance_at_500ft", root / "attempt",
                control_factory=lambda **kwargs: kwargs, camera_factory=FakeCameras)
            self.assertEqual(len(self.ego.controls), 900)
            self.assertEqual(len(self.approach.controls), 900)
            self.assertEqual(self.ego.controls[0]["brake"], 0.0)

    def test_returned_work_tree_is_rejected_as_attempt_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "site.json"
            path.write_text(json.dumps(site()) + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "under pipeline output root"):
                capture_original_carla(
                    self.world, self.ego, self.approach, path, digest, loc,
                    ASSIGNMENT + "__distance_at_500ft",
                    Path(__file__).resolve().parents[1] / "attempt-tmp")
            self.assertEqual(self.world.frame, 0)


if __name__ == "__main__":
    unittest.main()
