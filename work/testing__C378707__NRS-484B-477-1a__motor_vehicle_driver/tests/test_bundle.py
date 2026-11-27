"""Offline bundle identity and exact source-content check."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check


class BundleTests(unittest.TestCase):
    def test_exact_bundle(self):
        root = Path(__file__).resolve().parents[1]
        config = check(root)
        self.assertEqual(config["case"]["case_id"], config["selected_case_id"])
        self.assertEqual(config["case"]["recording_description"], config["recording_description"])
        plan = json.loads((root / "case-plan.json").read_text())
        self.assertIn(config["selected_case_id"], {c["case_id"] for c in plan["cases"]})


if __name__ == "__main__":
    unittest.main()
