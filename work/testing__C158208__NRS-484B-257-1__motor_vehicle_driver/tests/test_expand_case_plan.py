"""Check the full provisional case plan against immutable assignment identity."""

import json
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from expand_case_plan import expand


class ExpandCasePlanTests(unittest.TestCase):
    def test_frozen_cases_and_branch_comparisons(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        matrix = json.loads((HERE / "statutory-matrix.draft.json").read_text())
        frozen = json.loads((HERE.parents[1] / "inputs" / HERE.name / "assignment.json").read_text())
        expanded = expand(plan, matrix, frozen)
        expected = set(matrix["accepted_recordings"])
        self.assertEqual({case["case_id"] for case in expanded["cases"]}, expected)
        self.assertTrue(all(set(row["case_ids"]) <= expected and len(row["case_ids"]) >= 2
                            for row in expanded["comparisons"]))
        self.assertTrue({row["branch_id"] for row in matrix["branches"]} <=
                        {row["comparison_id"] for row in expanded["comparisons"]})
        self.assertEqual(len(expanded["cases"]), len(expand(expanded, matrix, frozen)["cases"]))

    def test_no_unfrozen_case_admitted(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        matrix = json.loads((HERE / "statutory-matrix.draft.json").read_text())
        frozen = json.loads((HERE.parents[1] / "inputs" / HERE.name / "assignment.json").read_text())
        plan["cases"].append({"case_id": HERE.name + "__fabricated"})
        with self.assertRaisesRegex(ValueError, "unfrozen"):
            expand(plan, matrix, frozen)


if __name__ == "__main__":
    unittest.main()
