import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_parking import control, phase_for, verify_road_feature, verify_traffic_actor
from runner import config


class BundleTests(unittest.TestCase):
    def test_native_feature_readback_rejects_declared_only_feature(self):
        class Location:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        Carla = type("Carla", (), {"Location": Location})

        class Map:
            def get_waypoint(self, location):
                yaw = 20 if location.x > 0 else 0
                return type("Waypoint", (), {"road_id": 17, "lane_width": 2.8,
                    "transform": type("Transform", (), {"rotation": type("Rotation", (),
                        {"yaw": yaw})()})()})()

        samples = [{"x": x, "y": 0, "road_id": 17, "lane_width_m": 2.8,
                    "heading_deg": heading} for x, heading in ((-1, 0), (1, 20))]
        place = {"feature": "curve", "feature_measurement": {"samples": samples}}
        self.assertEqual(verify_road_feature(Map(), Carla, place)["sample_count"], 2)
        place["feature_measurement"]["samples"][1]["heading_deg"] = 0
        with self.assertRaisesRegex(ValueError, "geometry differs"):
            verify_road_feature(Map(), Carla, place)

    def test_native_traffic_pose_readback(self):
        pose = {"x": 2, "y": 3, "z": 0, "yaw_deg": 15}
        actor = type("Actor", (), {"get_transform": lambda self: type("Transform", (),
            {"location": type("Location", (), {"x": 2, "y": 3, "z": 0})(),
             "rotation": type("Rotation", (), {"yaw": 15})()})()})()
        verify_traffic_actor(actor, pose)
        pose["x"] = 4
        with self.assertRaisesRegex(ValueError, "pose differs"):
            verify_traffic_actor(actor, pose)

    def test_frozen_case_and_halt_control(self):
        value = config()
        self.assertIn(value["case"]["requested_conduct"], ("stop", "stand", "park"))
        self.assertEqual(value["rate_hz"], 20)
        self.assertEqual(control(0.5, 0, "hold", "park"),
                         {"throttle": 0.0, "brake": 1.0, "hand_brake": True})
        self.assertFalse(control(0.5, 0, "hold", "stand")["hand_brake"])
        self.assertGreater(control(0, 0, "depart", "stop")["throttle"], 0)

    def test_approach_brakes_from_measured_distance(self):
        self.assertEqual(control(1, 5, "approach", "stop")["brake"], 0.65)
        self.assertGreater(control(20, 0, "approach", "stop")["throttle"], 0)

    def test_conduct_episodes_have_distinct_engineering_sequences(self):
        self.assertEqual(phase_for("stop", True, 60, 400), "depart")
        self.assertEqual(phase_for("stand", True, 60, 400), "hold")
        self.assertEqual(phase_for("stand", True, 160, 400), "depart")
        self.assertEqual(phase_for("park", True, 399, 400), "hold")


if __name__ == "__main__":
    unittest.main()
