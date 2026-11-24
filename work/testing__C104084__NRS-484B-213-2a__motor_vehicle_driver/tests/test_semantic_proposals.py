"""Guard the four exact crest branches and controlled differences."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location("c104084_semantic", ROOT / "build_semantic_proposals.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SemanticProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assignment = json.loads((PROJECT / "inputs" / ROOT.name / "assignment.json").read_text())
        cls.plan = json.loads((ROOT / "case-plan.json").read_text())
        cls.quote = json.loads((PROJECT / "inputs" / "coverage" / "branch-sources.json").read_text())["laws"][MODULE.LAW]["law"]["text"]

    def test_exact_law_and_comparison_isolation(self):
        stages = MODULE.prepare(self.assignment, self.plan, self.quote)
        self.assertEqual(stages["template"]["quote"], self.quote)
        self.assertEqual(len(stages["cases"]["cases"]), 4)
        self.assertEqual({c["changed_variable"] for c in stages["cases"]["comparisons"]}, set(MODULE.PAIR_VARIABLES.values()))
        self.assertTrue(all(c["unresolved_judgment_calls"] for c in stages["cases"]["cases"]))

    def test_quote_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["law_text"] = plan["law_text"].replace("one-way", "two-way")
        with self.assertRaisesRegex(ValueError, "frozen exact law"):
            MODULE.prepare(self.assignment, plan, self.quote)

    def test_comparison_crosses_two_variables_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["comparisons"][0]["case_ids"][1] = ROOT.name + "__left_crest_clear"
        with self.assertRaisesRegex(ValueError, "isolation changed"):
            MODULE.prepare(self.assignment, plan, self.quote)

    def test_case_omission_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["cases"].pop()
        with self.assertRaisesRegex(ValueError, "Four exact crest"):
            MODULE.prepare(self.assignment, plan, self.quote)


if __name__ == "__main__":
    unittest.main()
