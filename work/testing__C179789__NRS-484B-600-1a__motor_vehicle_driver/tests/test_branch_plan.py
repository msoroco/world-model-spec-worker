import hashlib
import json
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_branch_plan import CHANGES, REVIEW


class BranchPlanTests(unittest.TestCase):
    def test_frozen_comparison_and_exact_case_coverage(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        review = json.loads(REVIEW.read_text())
        by_id = {case["case_id"]: case for case in plan["cases"]}
        self.assertEqual(len(by_id), 7)
        self.assertEqual({row["comparison_id"] for row in plan["comparisons"]}, set(CHANGES))
        for planned in plan["comparisons"]:
            original = next(row for row in review["comparisons"] if row["id"] == planned["comparison_id"])
            self.assertEqual(planned["case_ids"], [row["case_id"] for row in original["cases"]])
            self.assertEqual(planned["deliberate_differences"], [CHANGES[planned["comparison_id"]]])
            self.assertTrue(planned["fixed_conditions"])
            self.assertEqual(planned["source_ref"]["sha256"], hashlib.sha256(REVIEW.read_bytes()).hexdigest())
        self.assertTrue(all(case["legal_judgment"] == "unresolved" for case in by_id.values()))


if __name__ == "__main__":
    unittest.main()
