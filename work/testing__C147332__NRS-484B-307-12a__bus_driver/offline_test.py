"""Tests materialized by runtime.py offline with each exact case bundle."""
import json
from pathlib import Path
import unittest

from runner import check
from native_driver import control_request


class ExactGreenArrowCase(unittest.TestCase):
    def test_road_route_and_two_heads(self):
        scene, road, static = check(Path("scene.json"))
        self.assertEqual(road, Path("road.xodr").resolve())
        self.assertTrue(static["bus_route_target_checked"])
        self.assertTrue(static["signal_geometry_target_checked"])
        self.assertEqual(len(scene["signals"]), 2)
        self.assertFalse(static["native_motion_verified"])
        config = json.loads(Path("config.json").read_text())
        self.assertEqual(config["selected_case_id"], scene["case_id"])
        self.assertEqual(len(config["cameras"]), 4)

    def test_controller_motion_and_hold(self):
        scene, _, _ = check(Path("scene.json"))
        x, y = scene["route_waypoint_centers_m"][0]
        request = control_request(scene, x_m=x, y_m=y, yaw_deg=0, speed_mps=0)
        if scene["case_id"].endswith("__green_selected_stand"):
            self.assertEqual(request["brake"], 1.0)
            self.assertEqual(request["throttle"], 0.0)
        else:
            self.assertGreater(request["throttle"], 0)
            self.assertEqual(request["target_lateral_m"], y)


if __name__ == "__main__":
    unittest.main()
