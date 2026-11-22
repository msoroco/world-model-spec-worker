"""Materialized exact pedestrian construction checks, without CARLA."""
import json
from pathlib import Path
import unittest

from native_capture import CAMERA_SPECS, camera_placements
from runner import FRAMES, check_scene


class OfflineConstructionTests(unittest.TestCase):
    def test_exact_case_map_walker_and_four_camera_plan(self):
        root = Path(__file__).resolve().parents[1]
        scene = check_scene(root/"scene.json", root/"candidate-corridor.xodr")
        config = json.loads((root/"config.json").read_text())
        self.assertEqual(scene["case_id"], config["selected_case_id"])
        self.assertEqual(config["actor"], "pedestrian")
        self.assertEqual(config["rate_hz"], 20)
        self.assertEqual(round(config["duration_s"]*20), FRAMES)
        self.assertEqual([camera["name"] for camera in config["cameras"]], list(CAMERA_SPECS))
        self.assertEqual(set(camera_placements(scene)), set(CAMERA_SPECS))
        self.assertEqual(len(scene["pedestrian_route_xy_m"]), 3)
