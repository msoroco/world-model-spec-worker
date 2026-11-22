"""Materialized exact case source and route tests for runtime.py offline."""
import json
import unittest
from pathlib import Path

from runner import check
from native_construction import check_road


class ExactRedXLaneCase(unittest.TestCase):
    def test_original_map_lane_route_and_head(self):
        scene, road, static = check(Path("scene.json"))
        self.assertEqual(road, Path("road.xodr").resolve())
        self.assertEqual(check_road(road)["lane_ids"], [-1, -2])
        self.assertTrue(static["bus_route_target_checked"])
        self.assertTrue(static["signal_geometry_target_checked"])
        self.assertFalse(static["native_motion_verified"])
        config = json.loads(Path("config.json").read_text())
        self.assertEqual(config["selected_case_id"], scene["case_id"])
        self.assertEqual(len(config["cameras"]), 4)


if __name__ == "__main__":
    unittest.main()
