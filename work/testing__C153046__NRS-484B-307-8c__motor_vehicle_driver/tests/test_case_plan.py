"""Check isolated C153046 draft controls without claiming realization."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_case_plan import KINDS, OBSERVATIONS, PAIRS, build


class PlanTests(unittest.TestCase):
    def test_exact_attempts_and_pair_isolation(self):
        plan = build()
        cases = {case["case_id"].removeprefix(plan["assignment_id"] + "__"): case
                 for case in plan["cases"]}
        self.assertEqual(set(cases), set(KINDS))
        self.assertEqual({row["comparison_id"] for row in plan["comparisons"]}, set(PAIRS))
        for name, (left, right, _) in PAIRS.items():
            self.assertEqual(sum(cases[left]["draft_variables"][key] !=
                                 cases[right]["draft_variables"][key]
                                 for key in cases[left]["draft_variables"]), 1, name)
        self.assertTrue(all(case["physical_acceptance_claimed"] is False
                            for case in cases.values()))

    def test_law_observations_and_uncertainty_retained(self):
        plan = build()
        self.assertEqual({row["term"] for row in plan["source_observation_mapping"]},
                         set(OBSERVATIONS))
        self.assertIn("must yield", plan["law_text"])
        self.assertEqual(plan["existing_evidence"], [])
        self.assertTrue(all(row["status"] == "source_review_or_original_capture_pending"
                            for row in plan["observations"]))


if __name__ == "__main__":
    unittest.main()
