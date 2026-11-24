"""Check exact source binding and comparison isolation in semantic proposals."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location("c109035_semantic", ROOT / "build_semantic_proposals.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SemanticProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assignment = json.loads((PROJECT / "inputs" / ROOT.name / "assignment.json").read_text())
        cls.plan = json.loads((ROOT / "case-plan.json").read_text())

    def test_exact_branches_and_comparisons(self):
        stages = MODULE.prepare(self.assignment, self.plan)
        self.assertEqual(stages["template"]["quote"], self.plan["law_text"])
        cases = stages["cases"]["cases"]
        self.assertEqual({c["case_id"] for c in cases}, {c["case_id"] for c in self.plan["cases"]})
        self.assertEqual(len(stages["cases"]["comparisons"]), 3)
        self.assertTrue(all(c["status"] == "draft" for c in cases))
        self.assertTrue(all(c["unresolved_judgment_calls"] for c in cases))

    def test_changed_device_request_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["cases"][0]["requested_siren"] = False
        with self.assertRaisesRegex(ValueError, "variables changed"):
            MODULE.prepare(self.assignment, plan)

    def test_omitted_law_clause_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["law_text"] = plan["law_text"].replace("not less than 500 feet", "")
        with self.assertRaisesRegex(ValueError, "Missing exact-law clause"):
            MODULE.prepare(self.assignment, plan)

    def test_comparison_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["comparisons"][1]["case_ids"].append(plan["cases"][1]["case_id"])
        with self.assertRaisesRegex(ValueError, "Comparison variables changed"):
            MODULE.prepare(self.assignment, plan)


if __name__ == "__main__":
    unittest.main()
