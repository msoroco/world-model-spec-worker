import copy
import json
import unittest
from pathlib import Path
from runner import check, control, read_survey


class BranchNativeContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_case_window_and_sources(self):
        result = check(self.config)
        self.assertEqual(result["case_id"], "training__C230266__NRS-484B-280-1c__motor_vehicle_driver__school_crossing_caution")
        self.assertEqual((result["branch"], result["mode"]), ("school_crossing", "caution"))
        self.assertEqual((result["frames"], result["rate_hz"]), (600, 20))
        self.assertEqual(len(result["source_views"]), 4)
        self.assertFalse(result["physical_completion"])

    def test_wrong_identity_short_window_and_missing_camera_rejected(self):
        for key, value in (("law_id", "NRS-484B-280-1a"), ("frames", 599),
                           ("physical_completion", True), ("legal_verdict", "compliant")):
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)
        bad = copy.deepcopy(self.config)
        bad["cameras"].pop()
        with self.assertRaises(ValueError):
            check(bad)

    def test_source_and_control(self):
        with self.assertRaises(FileNotFoundError):
            read_survey("missing-original-context-survey.json")
        self.assertEqual(control(25, 8)["phase"], "approach_request")
        self.assertEqual(control(10, 8)["phase"], "slow_request")
        with self.assertRaisesRegex(ValueError, "Measured"):
            control(float("nan"), 8)


if __name__ == "__main__":
    unittest.main()
