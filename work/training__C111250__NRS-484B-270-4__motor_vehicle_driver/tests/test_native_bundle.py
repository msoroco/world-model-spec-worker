import json
import unittest
from pathlib import Path
from runner import check
from route_v2 import check as route_check
class Bundle(unittest.TestCase):
    def test_exact_construction(self):
        config=json.loads(Path("config.json").read_text())
        self.assertTrue(check(config)["passed"])
        self.assertTrue(route_check()["passed"])
    def test_unprepared_camera_placement_rejected(self):
        config=json.loads(Path("config.json").read_text())
        config["camera_lateral_shift_m"]=9
        with self.assertRaises(ValueError): check(config)
