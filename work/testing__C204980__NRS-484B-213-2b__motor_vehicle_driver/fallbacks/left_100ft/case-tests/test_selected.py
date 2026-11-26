import json
import unittest
from pathlib import Path

class ExactRailCaseTest(unittest.TestCase):
    def test_selected_case_and_camera_contract(self):
        cfg=json.loads(Path("config.json").read_text())
        self.assertEqual(cfg["selected_case_id"],'testing__C204980__NRS-484B-213-2b__motor_vehicle_driver__left_100ft')
        self.assertEqual(cfg["rate_hz"]*cfg["duration_s"],900)
        self.assertEqual([x["name"] for x in cfg["cameras"]],["overview","approach","reference_corner","driver_reference"])
