import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("median_source", ROOT / "median_source.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def scene():
    return {
        "review_status": "reviewed_original", "reviewer": "source reviewer",
        "cell_id": "C125697", "actor": "motor_vehicle_driver",
        "law_id": "NRS-484B-250-2", "case_id": ROOT.name + "__timing_inside_training",
        "crossing": {"id": "reviewed-crossing", "kind": "median_opening_roadway_crossing",
                     "bounds_xy_m": [-2, -2, 2, 2],
                     "opendrive_sha256": hashlib.sha256(b"original-map").hexdigest()},
        "ego_highway": "public-a", "other_highway": "public-b",
        "ego_approach_road_id": 11, "other_approach_road_id": 12,
        "ego_route_xy_m": [[-10, 0], [0, 0], [10, 0]],
        "other_route_xy_m": [[0, 10], [0, 0], [0, -10]],
        "ego_approach_side": "left", "other_approach_side": "right",
        "governing_signal": {"kind": "official_traffic_signal", "actor_id": 41,
                             "readback_state": "inoperative", "controls_traffic": False,
                             "controlled_approach_road_ids": [11, 12]},
        "opposing_left_turn_excluded_source": "reviewed original route vectors",
        "subsection_4_applicability_review": "separate legal applicability review pending",
    }


class Map:
    def to_opendrive(self):
        return "original-map"

    def get_waypoint(self, point, project_to_road=False):
        if project_to_road is not False:
            raise AssertionError("route projection would hide source mismatch")
        x, y = point
        road = 11 if abs(x) >= abs(y) else 12
        return SimpleNamespace(
            road_id=road, is_junction=abs(x) < 2 and abs(y) < 2,
            transform=SimpleNamespace(location=SimpleNamespace(x=x, y=y)))


class MedianSourceTests(unittest.TestCase):
    def test_reviewed_crossing_and_reversed_approach(self):
        original = scene()
        result = module.validate_scene(original, "original-map", lambda x, y: (x, y), Map())
        self.assertEqual(result["approach_sides"], ("left", "right"))
        reversed_scene = scene()
        reversed_scene["ego_route_xy_m"], reversed_scene["other_route_xy_m"] = (
            reversed_scene["other_route_xy_m"], reversed_scene["ego_route_xy_m"])
        reversed_scene["ego_approach_road_id"], reversed_scene["other_approach_road_id"] = 12, 11
        reversed_scene["ego_highway"], reversed_scene["other_highway"] = "public-b", "public-a"
        reversed_scene["ego_approach_side"], reversed_scene["other_approach_side"] = "right", "left"
        self.assertEqual(module.validate_scene(reversed_scene, "original-map",
                                               lambda x, y: (x, y), Map())["approach_sides"],
                         ("right", "left"))

    def test_source_guards(self):
        for field, value, expected in (
            ("review_status", "authored", "reviewed original"),
            ("ego_approach_side", "right", "left/right"),
            ("ego_highway", "public-b", "different"),
        ):
            with self.subTest(field=field):
                changed = scene()
                changed[field] = value
                with self.assertRaisesRegex(ValueError, expected):
                    module.validate_scene(changed, "original-map")
        with self.assertRaisesRegex(ValueError, "OpenDRIVE differs"):
            module.validate_scene(scene(), "changed-map")
        changed = scene()
        changed["governing_signal"]["controls_traffic"] = True
        with self.assertRaisesRegex(ValueError, "inoperative governing signal"):
            module.validate_scene(changed, "original-map")

    def test_original_device_and_highway_bytes_bound(self):
        scratch = Path(".runtime-work/c125697-2502-tests").resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            original = scene()
            sources = {
                "device_inventory": {"governing_signal_actor_id": 41,
                                     "controlled_approach_road_ids": [11, 12]},
                "highway_identity": {"ego_highway": "public-a", "other_highway": "public-b",
                                     "public_access_confirmed": True},
            }
            original["source_refs"] = {}
            for name, body in sources.items():
                raw = json.dumps(body).encode()
                (root / (name + ".json")).write_bytes(raw)
                original["source_refs"][name] = {
                    "path": name + ".json", "sha256": hashlib.sha256(raw).hexdigest(),
                    "citation": "reviewed original " + name}
            packet = root / "site.json"
            packet.write_text(json.dumps(original))
            bound, raw_sources = module.reviewed_packet(packet, Map(), lambda x, y: (x, y))
            self.assertEqual(bound["case_id"], original["case_id"])
            self.assertEqual(raw_sources["opendrive"], b"original-map")
            (root / "device_inventory.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "device inventory source changed"):
                module.reviewed_packet(packet, Map(), lambda x, y: (x, y))

    def test_complete_original_native_entry_measurement(self):
        original = scene()
        def body(x):
            return [[x - .4, -.4], [x + .4, -.4], [x + .4, .4], [x - .4, .4]]
        frames = []
        for index in range(900):
            frames.append({
                "frame": index, "time_s": index / 20,
                "native_frame_id": index + 100, "native_elapsed_seconds": 20 + index / 20,
                "signal_readback": "inoperative",
                "ego": {"id": 1, "road_id": 11,
                        "body_vertices_xy_m": body(0 if index >= 3 else -10)},
                "other": {"id": 2, "road_id": 12,
                          "body_vertices_xy_m": body(0 if index >= 2 else 10)},
            })
        trace = {"case_id": original["case_id"],
                 "map_sha256": original["crossing"]["opendrive_sha256"],
                 "actor_ids": {"ego": 1, "other": 2}, "frames": frames}
        observation = module.measure_saved(trace, original)
        self.assertEqual(observation["ego_entry"]["upper_frame"], 103)
        self.assertEqual(observation["other_entry"]["upper_frame"], 102)
        self.assertAlmostEqual(observation["intersection_entry_time_difference_s"], .05)
        self.assertIsNone(observation["legal_judgment"])
        changed = json.loads(json.dumps(trace))
        changed["frames"][12]["native_frame_id"] += 1
        with self.assertRaisesRegex(ValueError, "frame/clock discontinuity"):
            module.measure_saved(changed, original)
        changed = json.loads(json.dumps(trace))
        changed["frames"][12]["signal_readback"] = "green"
        with self.assertRaisesRegex(ValueError, "signal changed"):
            module.measure_saved(changed, original)


if __name__ == "__main__":
    unittest.main()
