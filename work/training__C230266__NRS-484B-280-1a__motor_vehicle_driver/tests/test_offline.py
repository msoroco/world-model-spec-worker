import copy
import json
import unittest
from pathlib import Path

from runner import CASES, check, control


class SelectedRoadPedestrianOffline(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_source_and_window(self):
        result = check(self.config)
        self.assertEqual(result["case_id"], self.config["case_id"])
        self.assertEqual((result["frames"], result["rate_hz"]), (600, 20))
        self.assertEqual(len(result["source_views"]), 4)
        self.assertFalse(result["carla_contacted"])

    def test_comparison_control_is_fixed_by_case(self):
        self.assertEqual(CASES[self.config["case_id"]], self.config["controller"])
        response = control(10, 8, self.config["controller"])
        self.assertEqual(response["brake"] > 0,
                         self.config["controller"] == "distance_triggered_slow_request")
        self.assertEqual(control(25, 8, self.config["controller"])["brake"], 0)

    def test_wrong_identity_or_response_rejected(self):
        for key, value in (("case_id", "wrong"), ("law_id", "NRS-484B-280-1c"),
                           ("controller", "wrong"), ("frames", 599)):
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)

    def test_camera_removed_rejected(self):
        bad = copy.deepcopy(self.config)
        bad["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four named"):
            check(bad)


if __name__ == "__main__":
    unittest.main()
