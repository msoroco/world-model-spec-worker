import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from source_inventory import REQUIRED, audit


class SourceInventoryTests(unittest.TestCase):
    def test_all_three_frozen_memberships_are_unverified(self):
        report = audit(REPO)
        self.assertEqual(len(report["accepted_sources"]), 3)
        for entry in report["accepted_sources"]:
            self.assertEqual(entry["available_original_source_hashes"], {})
            self.assertEqual(tuple(entry["missing_required_original_sources"]), REQUIRED)
            self.assertFalse(entry["law_coverage_verified"])
            self.assertFalse(entry["reuse_selected"])

    def test_case_plan_keeps_all_six_ids(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        self.assertEqual(len(plan["cases"]), 6)
        self.assertEqual(len(plan["comparisons"]), 5)
        self.assertEqual({case["source_disposition"]["status"] for case in plan["cases"]},
                         {"unverified_existing_evidence", "selected_source_gated_construction"})


if __name__ == "__main__":
    unittest.main()
