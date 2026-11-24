"""Check frozen-law, exact-case and isolated comparison semantics."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location("c111278_semantic", ROOT / "build_semantic_proposals.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assignment = json.loads((PROJECT / "inputs" / ROOT.name / "assignment.json").read_text())
        cls.plan = json.loads((ROOT / "case-plan.json").read_text())
        cls.quote = json.loads((PROJECT / "inputs" / "coverage" / "branch-sources.json").read_text())["laws"][MODULE.LAW]["law"]["text"]

    def test_exact_cases_and_independent_exceptions(self):
        stages = MODULE.prepare(self.assignment, self.plan, self.quote)
        self.assertEqual(len(stages["cases"]["cases"]), 6)
        self.assertEqual(len(stages["cases"]["comparisons"]), 4)
        self.assertEqual({row["changed_variable"] for row in stages["cases"]["comparisons"]}, set(MODULE.VARS))
        self.assertEqual(len(stages["template"]["structure"]["exceptions"]), 2)

    def test_quote_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["law_text"] = plan["law_text"].replace("fifteen", "twenty")
        with self.assertRaisesRegex(ValueError, "frozen exact law"):
            MODULE.prepare(self.assignment, plan, self.quote)

    def test_case_target_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["cases"][0]["requested_traversal_speed_mph"] = 15
        with self.assertRaisesRegex(ValueError, "variables changed"):
            MODULE.prepare(self.assignment, plan, self.quote)

    def test_pair_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["comparisons"][2]["case_ids"][1] = ROOT.name + "__controlled_blocked"
        with self.assertRaisesRegex(ValueError, "comparison variables changed"):
            MODULE.prepare(self.assignment, plan, self.quote)


if __name__ == "__main__":
    unittest.main()
