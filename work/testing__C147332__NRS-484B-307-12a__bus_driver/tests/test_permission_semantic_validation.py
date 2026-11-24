"""Scope checks for the proposed permission-only semantic repair."""
import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from permission_semantic_validation import validate


class PermissionSemanticTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((ROOT / "proposals/template.json").read_text())
        self.cases = json.loads((ROOT / "proposals/cases.json").read_text())
        self.plan = json.loads((ROOT / "case-plan.json").read_text())
        self.assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())

    def test_exact_permission_pairs_pass_without_legal_verdict(self):
        proof = validate(self.template, self.cases, self.plan, self.assignment)
        self.assertEqual(len(proof["case_ids"]), 4)
        self.assertFalse(proof["legal_verdict_claimed"])

    def test_duty_template_cannot_use_permission_path(self):
        template = copy.deepcopy(self.template)
        template["structure"]["obligation"]["type"] = "duty"
        with self.assertRaisesRegex(ValueError, "permission template"):
            validate(template, self.cases, self.plan, self.assignment)

    def test_unsupported_violating_label_rejected(self):
        cases = copy.deepcopy(self.cases)
        cases["cases"][2]["target_type"] = "violating_attempt"
        with self.assertRaisesRegex(ValueError, "identity/type"):
            validate(self.template, cases, self.plan, self.assignment)

    def test_changed_fixed_variable_rejected(self):
        cases = copy.deepcopy(self.cases)
        cases["cases"][3]["variable_assignments"]["bus_motion_request"]["value"] = "stand"
        with self.assertRaisesRegex(ValueError, "undeclared variable"):
            validate(self.template, cases, self.plan, self.assignment)

    def test_duplicate_proposed_case_rejected(self):
        cases = copy.deepcopy(self.cases)
        cases["cases"].append(copy.deepcopy(cases["cases"][1]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate(self.template, cases, self.plan, self.assignment)

    def test_omitted_planned_case_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["cases"].pop()
        with self.assertRaisesRegex(ValueError, "plan case identity"):
            validate(self.template, self.cases, plan, self.assignment)

    def test_duplicate_comparison_and_probe_declaration_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan['comparisons'].append(copy.deepcopy(plan['comparisons'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate permission comparison'):
            validate(self.template, self.cases, plan, self.assignment)
        cases = copy.deepcopy(self.cases)
        cases['cases'][2]['probe']['primary_variable'] = 'bus_lane_request'
        with self.assertRaisesRegex(ValueError, 'probe declaration'):
            validate(self.template, cases, self.plan, self.assignment)

    def test_comparison_description_drift_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan['comparisons'][0]['deliberate_differences'] = ['another change']
        with self.assertRaisesRegex(ValueError, 'description differs'):
            validate(self.template, self.cases, plan, self.assignment)


if __name__ == "__main__":
    unittest.main()
