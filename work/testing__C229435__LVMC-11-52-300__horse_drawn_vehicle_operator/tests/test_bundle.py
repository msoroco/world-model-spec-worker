"""Portable selected-case offline guards."""
import json
import unittest
from pathlib import Path

class SelectedBundleTests(unittest.TestCase):
    def test_case_binding_and_original_site_guard(self):
        if not Path("config.json").is_file():
            self.skipTest("selected bundle is materialized only by offline check")
        from runner import reviewed_plan, selected_config
        value = selected_config()
        self.assertEqual(value["case"]["case_id"], value["selected_case_id"])
        self.assertEqual(value["case"]["design"]["other_vehicle"],
                         "present; original body and state required")
        self.assertEqual(len(value["cameras"]), 4)
        with self.assertRaisesRegex(ValueError, "reviewed original site"):
            reviewed_plan(value)
        construction = json.loads(Path("construction.json").read_text())
        self.assertEqual(construction["case_id"], value["selected_case_id"])


if __name__ == "__main__":
    unittest.main()
