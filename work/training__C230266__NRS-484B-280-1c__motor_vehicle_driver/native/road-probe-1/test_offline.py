import copy
import json
import unittest
from pathlib import Path

from runner import check, control, read_survey


class DraftNativeContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_window_and_sources(self):
        result = check(self.config)
        self.assertEqual((result["frames"], result["rate_hz"]), (600, 20))
        self.assertEqual(len(result["source_views"]), 4)
        self.assertFalse(result["carla_contacted"])
        self.assertFalse(result["physical_completion"])

    def test_wrong_identity_or_short_window_rejected(self):
        for key, value in (("law_id", "NRS-484B-280-1a"), ("frames", 599),
                           ("physical_completion", True), ("legal_verdict", "compliant")):
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)

    def test_missing_camera_rejected(self):
        bad = copy.deepcopy(self.config)
        bad["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four named"):
            check(bad)

    def test_source_and_control(self):
        with self.assertRaises(FileNotFoundError):
            read_survey("missing-original-road-survey.json")
        self.assertEqual(control(25, 8)["phase"], "approach_request")
        self.assertEqual(control(10, 8)["phase"], "slow_request")
        with self.assertRaisesRegex(ValueError, "Measured"):
            control(float("nan"), 8)


if __name__ == "__main__":
    unittest.main()
