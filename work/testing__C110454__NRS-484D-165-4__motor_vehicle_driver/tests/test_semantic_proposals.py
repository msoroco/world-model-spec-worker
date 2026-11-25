"""Check frozen-text and exact lamp-mode semantic bindings."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location("c110454_semantic", ROOT / "build_semantic_proposals.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assignment = json.loads((PROJECT / "inputs" / ROOT.name / "assignment.json").read_text())
        cls.plan = json.loads((ROOT / "case-plan.json").read_text())
        cls.quote = json.loads((PROJECT / "inputs" / "coverage" / "branch-sources.json").read_text())["laws"][MODULE.LAW]["law"]["text"]

    def test_exact_cases_and_unresolved_aim(self):
        stages = MODULE.prepare(self.assignment, self.plan, self.quote)
        self.assertEqual(len(stages["cases"]["cases"]), 4)
        self.assertEqual(stages["cases"]["cases"][0]["target_type"], "baseline")
        self.assertEqual(len(stages["cases"]["comparisons"]), 2)
        self.assertTrue(all("depressed or dimmed" in case["unresolved_judgment_calls"]
                            for case in stages["cases"]["cases"][1:]))

    def test_quote_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["law_text"] = plan["law_text"].replace("depressed or dimmed", "bright")
        with self.assertRaisesRegex(ValueError, "frozen law"):
            MODULE.prepare(self.assignment, plan, self.quote)

    def test_lamp_request_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["cases"][1]["requested_headlamp_mode"] = "high_beam"
        with self.assertRaisesRegex(ValueError, "variables changed"):
            MODULE.prepare(self.assignment, plan, self.quote)

    def test_comparison_membership_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["comparisons"][0]["case_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "membership changed"):
            MODULE.prepare(self.assignment, plan, self.quote)


if __name__ == "__main__":
    unittest.main()
