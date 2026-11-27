"""Offline materialized bundle checks without CARLA."""
import json
import unittest
from pathlib import Path

from runner import check_config
from cycle_lane_native import control
from cycle_lane_2703 import intersects


class BundleTest(unittest.TestCase):
    def test_exact_config_controller_and_body_geometry(self):
        cfg=json.loads(Path("config.json").read_text())
        self.assertTrue(check_config(cfg))
        self.assertTrue(control((-3,0),0,0,[[-3,0],[1,0]])["throttle"] > 0)
        self.assertTrue(control((-3,0),0,0,[[-3,0],[1,0]],park=True)["hand_brake"])
        self.assertTrue(intersects([[-2,-.1],[2,-.1],[2,.1],[-2,.1]],
                                   [[-.1,-2],[.1,-2],[.1,2],[-.1,2]]))


if __name__=="__main__":
    unittest.main()
