"""CPU checks of source binding, footprints, controllers and actual measurements."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stop_model", ROOT / "stop_model.py")
MODEL = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODEL
SPEC.loader.exec_module(MODEL)


def fixture_scene():
    return {"roadway_polygon": [[0, 0], [100, 0], [100, 4], [0, 4]],
            "shoulder_polygon": [[0, 5], [100, 5], [100, 8], [0, 8]],
            "sources": {"stop_purpose": {"sha256": "a" * 64},
                        "jurisdiction": {"sha256": "b" * 64}}}


class ModelTests(unittest.TestCase):
    def test_reviewed_packet_requires_every_original_source(self):
        required = ("map", "roadway_boundary", "shoulder_boundary", "one_way_direction",
                    "ego_driver", "ego_vehicle", "follower_vehicle", "follower_driver",
                    "stop_purpose", "conflict_context", "official_direction",
                    "jurisdiction", "passing_space")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {}
            for name in required:
                path = root / (name + ".json")
                path.write_text(json.dumps({"name": name}) + "\n")
                sources[name] = {"path": path.name,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            case_id = MODEL.ASSIGNMENT + "__destination_follower_halts"
            packet = {"format": "c150640-roadway-stop-original-v1",
                      "case_id": case_id, "source_kind": "original_reviewed",
                      "diagnostic_fixture": False, "reviewer": "local site reviewer",
                      "sources": sources, "map_id": "reviewed map",
                      "ego_blueprint_id": "vehicle.ego",
                      "follower_blueprint_id": "vehicle.follower",
                      "one_way_route": [[1, 2], [40, 2]],
                      "route_direction_confirmed": True,
                      "ego_spawn_xy": [1, 2], "follower_spawn_xy": [0, 2],
                      "ego_stop_xy": [25, 2], "follower_pass_route": [[0, 2], [40, 3]],
                      "passing_space_m": 3,
                      **fixture_scene()}
            packet["sources"] = sources
            target = root / "packet.json"
            target.write_text(json.dumps(packet) + "\n")
            self.assertEqual(MODEL.reviewed_scene(target, case_id)["case_id"], case_id)
            (root / "passing_space.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "hash differs: passing_space"):
                MODEL.reviewed_scene(target, case_id)

    def test_roadway_shoulder_and_boundary_are_measured(self):
        scene = fixture_scene()
        self.assertEqual(MODEL.footprint_surface([[1, 1], [2, 1], [2, 2], [1, 2]], scene), "roadway")
        self.assertEqual(MODEL.footprint_surface([[1, 6], [2, 6], [2, 7], [1, 7]], scene), "shoulder")
        self.assertEqual(MODEL.footprint_surface([[1, 3], [2, 3], [2, 6], [1, 6]], scene),
                         "boundary_or_unresolved")

    def test_case_controllers_are_distinct_and_gap_sensitive(self):
        stop = MODEL.controller_target(MODEL.BY_NAME["destination_follower_halts"], 300, 3, 6, 8)
        roll = MODEL.controller_target(MODEL.BY_NAME["destination_slow_roll"], 300, 1, 6, 8)
        passing = MODEL.controller_target(MODEL.BY_NAME["destination_follower_passes"], 300, 3, 6, 8)
        self.assertGreater(stop["ego"]["brake"], roll["ego"]["brake"])
        self.assertGreater(stop["follower"]["brake"], passing["follower"]["brake"])
        early = MODEL.controller_target(MODEL.BY_NAME["destination_follower_halts"],
                                        180, 3, 6, 8, stop_trigger_frame=170)
        primary = MODEL.controller_target(MODEL.BY_NAME["destination_follower_halts"],
                                          180, 3, 6, 8, stop_trigger_frame=200)
        self.assertGreater(early["ego"]["brake"], primary["ego"]["brake"])

    def test_measurement_requires_two_original_participants_and_keeps_judgments_open(self):
        scene = fixture_scene()
        rows = []
        for i in range(8):
            rows.append({"original_frame": i + 10, "time_s": i * .05,
                         "ego_id": 1, "follower_id": 2,
                         "ego_speed_mps": 0 if i >= 3 else 4,
                         "follower_speed_mps": 2 if i >= 3 else 5,
                         "ego_footprint_xy": [[1, 1], [2, 1], [2, 2], [1, 2]],
                         "follower_route_station_m": float(i),
                         "body_gap_m": 10-i, "follower_ahead_of_ego": False,
                         "conflict_readback": None,
                         "official_direction_readback": None})
        measured = MODEL.measure_original(rows, scene, MODEL.CASES[0])
        self.assertTrue(measured["actual_complete_stop"])
        self.assertEqual(measured["stop_surfaces"], ["roadway"])
        self.assertIsNone(measured["statutory_verdict"])
        rows[3]["follower_id"] = 1
        with self.assertRaisesRegex(ValueError, "identities collapse"):
            MODEL.measure_original(rows, scene, MODEL.CASES[0])


if __name__ == "__main__":
    unittest.main()
