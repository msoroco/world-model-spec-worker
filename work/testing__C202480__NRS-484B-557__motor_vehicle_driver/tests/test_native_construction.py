import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

MODULE = Path(__file__).resolve().parents[1] / "native_construction.py"
SPEC = importlib.util.spec_from_file_location("native_construction", MODULE)
CONSTRUCT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONSTRUCT)


def site(root, case_id="case"):
    records = {
        "opendrive": b"reviewed map",
        "crossing_authority": json.dumps({"designation_authority": "state_dot", "crossing_type": "highway_railroad_grade",
                                           "device_type": "official_stop_sign", "device_governs": "railroad_approach",
                                           "sign_landmark_id": "sign-1"}).encode(),
        "crossing_geometry": json.dumps({"rail_id": "rail-1", "nearest_rail_xy_m": [0, 0],
                                          "approach_unit_normal_xy": [1, 0]}).encode(),
    }
    bindings = {}
    for name, data in records.items():
        path = root / f"{name}.json"
        path.write_bytes(data)
        bindings[name] = {"path": path.name, "sha256": hashlib.sha256(data).hexdigest()}
    packet = {"format": "nrs-484b-557-reviewed-site-v1", "case_id": case_id,
              "sources": bindings, "sign_landmark_id": "sign-1", "rail_id": "rail-1",
              "ego_longitudinal_half_extent_m": 2.0, "ego_blueprint_id": "vehicle.test"}
    path = root / "site.json"
    path.write_text(json.dumps(packet))
    return path, packet


class World:
    def __init__(self):
        self.spawned = []
        self.map_text = "reviewed map"
        self.signs = [SimpleNamespace(id="sign-1")]

    def get_map(self):
        return SimpleNamespace(to_opendrive=lambda: self.map_text, get_all_landmarks=lambda: self.signs)

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda x: x)

    def try_spawn_actor(self, blueprint, transform):
        self.spawned.append((blueprint, transform))
        return SimpleNamespace(id=1)


class NativeConstructionTest(unittest.TestCase):
    def test_spawn_requests_geometry_and_blueprint(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = site(Path(directory))
            world = World()
            case = {"case_id": "case", "planned_stop_body_gap_ft": 15.0}
            built = CONSTRUCT.create(world, path, case, lambda x, y, n: (x, y, n))
            self.assertEqual(len(world.spawned), 1)
            self.assertEqual(world.spawned[0][0], "vehicle.test")
            self.assertAlmostEqual(built["planned_center_xy_m"][0], -(2 + 15 / CONSTRUCT.FEET_PER_METRE))
            self.assertEqual(world.spawned[0][1][2], [1, 0])

    def test_unsupported_authority_rejected_before_spawn(self):
        with tempfile.TemporaryDirectory() as directory:
            path, packet = site(Path(directory))
            authority_path = Path(directory) / packet["sources"]["crossing_authority"]["path"]
            authority = json.loads(authority_path.read_text())
            authority["device_governs"] = "intersection"
            data = json.dumps(authority).encode()
            authority_path.write_bytes(data)
            packet["sources"]["crossing_authority"]["sha256"] = hashlib.sha256(data).hexdigest()
            path.write_text(json.dumps(packet))
            world = World()
            with self.assertRaisesRegex(ValueError, "governance"):
                CONSTRUCT.create(world, path, {"case_id": "case", "planned_stop_body_gap_ft": 15}, lambda *args: args)
            self.assertEqual(world.spawned, [])

    def test_source_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, packet = site(Path(directory))
            (Path(directory) / packet["sources"]["crossing_geometry"]["path"]).write_text("{}")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                CONSTRUCT.inspect_site(path, {"case_id": "case", "planned_stop_body_gap_ft": 15})

    def test_wrong_live_map_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = site(Path(directory))
            world = World()
            world.map_text = "other map"
            with self.assertRaisesRegex(ValueError, "live OpenDRIVE"):
                CONSTRUCT.create(world, path, {"case_id": "case", "planned_stop_body_gap_ft": 15}, lambda *args: args)

    def test_missing_live_sign_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = site(Path(directory))
            world = World()
            world.signs = []
            with self.assertRaisesRegex(ValueError, "stop sign absent"):
                CONSTRUCT.create(world, path, {"case_id": "case", "planned_stop_body_gap_ft": 15}, lambda *args: args)


if __name__ == "__main__":
    unittest.main()
