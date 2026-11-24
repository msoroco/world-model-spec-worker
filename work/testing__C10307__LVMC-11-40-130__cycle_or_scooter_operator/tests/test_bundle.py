import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner


class ReferenceBundleTests(unittest.TestCase):
    def test_reference_case_and_camera_contract(self):
        result = runner.check()
        self.assertIn(result["target_speed_mps"], (3.0, 5.0))
        self.assertEqual(result["route"], [[-30.0, -0.75], [30.0, -0.75]])
        self.assertFalse(result["capture_complete"])

    def test_wrong_case_is_rejected(self):
        config = json.loads((ROOT / "config.json").read_text())
        self.assertIn(config["selected_case_id"], config["supported_case_ids"])
        self.assertEqual(len(config["cameras"]), 4)


if __name__ == "__main__":
    unittest.main()
