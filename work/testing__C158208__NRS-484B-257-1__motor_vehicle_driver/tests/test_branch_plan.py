import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ASSIGNMENT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_branch_plan", ASSIGNMENT / "build_branch_plan.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BranchPlanTests(unittest.TestCase):
    def test_exact_frozen_comparison_and_metadata_bindings(self):
        plan = builder.build()
        self.assertEqual(len(plan["comparisons"]), 8)
        self.assertEqual(len(plan["exact_case_ids"]), 8)
        self.assertEqual(plan, json.loads((ASSIGNMENT / "branch-plan.json").read_text()))
        for comparison in plan["comparisons"]:
            for case in comparison["cases"]:
                source = builder.ROOT / case["metadata_source"]["path"]
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                                 case["metadata_source"]["sha256"])
                self.assertEqual(case["physical_sufficiency"], "unverified_from_export")


if __name__ == "__main__":
    unittest.main()
