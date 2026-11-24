import json
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]


class PlannedExactCasesTests(unittest.TestCase):
    def test_frozen_scope_and_planned_probe_alignment(self):
        plan = json.loads((PACKAGE / "case-plan.json").read_text())
        proposals = json.loads((PACKAGE / "proposals/cases.json").read_text())
        ids = [case["case_id"] for case in plan["cases"]]
        selected = [case["case_id"] for case in proposals["cases"]
                    if case["target_type"] != "baseline"]
        self.assertEqual(ids, selected)
        self.assertEqual(len(ids), 3)
        self.assertEqual(plan["neutral_reference"]["case_id"], proposals["cases"][0]["case_id"])
        self.assertEqual(plan["comparisons"][0]["case_ids"], ids)
        self.assertEqual(plan["comparisons"][0]["comparison_id"], "distance_500ft")
        self.assertTrue(all(case["planning_status"] == "source_review_pending"
                            for case in plan["cases"]))
        self.assertTrue(all(case["gap_ids"] == ["unverified-law-coverage"]
                            for case in plan["cases"]))
        self.assertTrue(all(case["physical_risk"]["status"] == "physical"
                            for case in plan["cases"]))


if __name__ == "__main__":
    unittest.main()
