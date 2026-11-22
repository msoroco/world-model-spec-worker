"""Exercise all exact source-bound construction and lazy controller calls."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_control import apply, step
from parking_pose import REQUESTS
from parking_scene import build
from test_source_review import fixture


class ParkingSceneControlTests(unittest.TestCase):
    def test_six_cases_require_matching_activity_source_and_preserve_pairs(self):
        with TemporaryDirectory() as tmp:
            packet_path, packet = fixture(tmp)
            scenes = {}
            for activity in ("park", "stand"):
                packet["context"]["activity"] = activity
                packet_path.write_text(json.dumps(packet))
                for suffix in REQUESTS:
                    if suffix.startswith(activity + "_"):
                        scenes[suffix] = build(packet_path, tmp, suffix)
                    else:
                        with self.assertRaisesRegex(ValueError, "activity differs"):
                            build(packet_path, tmp, suffix)
            self.assertEqual(len(scenes), 6)
            for activity in ("park", "stand"):
                lawful = scenes[activity + "_parallel_lawful"]
                angled = scenes[activity + "_angled_lawful"]
                reverse = scenes[activity + "_parallel_reverse"]
                for other in (angled, reverse):
                    self.assertEqual(lawful["target_pose"]["target_center_xy_m"],
                                     other["target_pose"]["target_center_xy_m"])
                    self.assertEqual(lawful["source_hashes"], other["source_hashes"])
                    self.assertFalse(other["physical_realization_claimed"])
                self.assertNotEqual(lawful["target_pose"]["target_forward_xy"],
                                    angled["target_pose"]["target_forward_xy"])
                self.assertLess(lawful["target_pose"]["target_forward_xy"][0] *
                                reverse["target_pose"]["target_forward_xy"][0], 0)

    def test_changed_source_and_outside_spawn_rejected(self):
        with TemporaryDirectory() as tmp:
            path, packet = fixture(tmp)
            with self.assertRaisesRegex(ValueError, "spawn body leaves"):
                build(path, tmp, "park_parallel_lawful", approach_distance_m=30)
            (Path(tmp) / "roadway.txt").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                build(path, tmp, "park_parallel_lawful")
            self.assertEqual(packet["review_status"], "reviewed")

    def test_shorter_approach_fits_when_primary_footprint_does_not(self):
        with TemporaryDirectory() as tmp:
            path, packet = fixture(tmp)
            packet["context"]["road_edge_xy_m"] = [[-10, 0], [10, 0]]
            packet["context"]["roadway_polygon_xy_m"] = [[-10, 0], [10, 0],
                                                              [10, 5], [-10, 5]]
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "spawn body leaves"):
                build(path, tmp, "park_parallel_lawful")
            alternate = build(path, tmp, "park_parallel_lawful",
                              approach_distance_m=6.0)
            self.assertEqual(alternate["spawn_center_xy_m"], [-6.0, 2.5])
            self.assertFalse(alternate["physical_realization_claimed"])

    def test_control_approach_brake_hold_and_lazy_native_call(self):
        with TemporaryDirectory() as tmp:
            path, _ = fixture(tmp)
            scene = build(path, tmp, "park_parallel_lawful")
            approaching = step(scene, {"center_xy_m": [-8, 2.5],
                                       "forward_xy": [1, 0], "speed_m_s": 2})
            self.assertEqual(approaching["phase"], "approach")
            self.assertGreater(approaching["throttle"], 0)
            braking = step(scene, {"center_xy_m": [0, 2.5],
                                    "forward_xy": [1, 0], "speed_m_s": 1})
            self.assertEqual(braking["phase"], "braking")
            held = step(scene, {"center_xy_m": [0, 2.5],
                                 "forward_xy": [1, 0], "speed_m_s": 0})
            self.assertEqual(held["phase"], "stationary_hold")
            self.assertFalse(held["realized_hold_claimed"])
            wrong = step(scene, {"center_xy_m": [0, 2.5],
                                  "forward_xy": [-1, 0], "speed_m_s": 0})
            self.assertEqual(wrong["phase"], "needs_maneuver_review")
            self.assertEqual(wrong["brake"], 1)

            class Carla:
                @staticmethod
                def VehicleControl(**values):
                    return values

            class Vehicle:
                def apply_control(self, control):
                    self.control = control

            vehicle = Vehicle()
            self.assertEqual(apply(vehicle, held, Carla), vehicle.control)
            self.assertEqual(vehicle.control["brake"], 1)

            angled = build(path, tmp, "park_angled_lawful")
            turn = step(angled, {"center_xy_m": [-2, 2.5],
                                 "forward_xy": [1, 0], "speed_m_s": 1})
            self.assertEqual(turn["phase"], "approach")
            self.assertGreater(turn["steer"], 0)


if __name__ == "__main__":
    unittest.main()
