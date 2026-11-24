"""The worker trial changes only the permission branch of the pinned coverage check."""
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from permission_runtime_trial import permission_aware_coverage, trial


class PermissionRuntimeTrialTests(unittest.TestCase):
    def setUp(self):
        self.assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        self.template = json.loads((ROOT / "proposals/template.json").read_text())
        self.proposal = json.loads((ROOT / "proposals/cases.json").read_text())
        self.plan = json.loads((ROOT / "case-plan.json").read_text())
        self.binding = json.loads((ROOT / "proposals/bindings.json").read_text())

    def call(self, template):
        return permission_aware_coverage(
            self.proposal["cases"], self.binding, [template], [],
            template=self.template, proposal=self.proposal, plan=self.plan,
            assignment=self.assignment)

    def test_full_pinned_stage_chain_passes_only_with_trial(self):
        report = trial()
        self.assertEqual(report["selected_cases"], 4)
        self.assertFalse(report["pinned_semantic_validator_passed"])
        self.assertFalse(report["pinned_semantic_runtime_modified"])

    def test_plain_duty_still_requires_compliant_violating_pair(self):
        duty = json.loads(json.dumps(self.template))
        duty["structure"]["obligation"]["type"] = "duty"
        with self.assertRaisesRegex(ValueError, "Missing plain-rule attempt pair"):
            self.call(duty)

    def test_permission_trial_rejects_altered_source_quote(self):
        changed = json.loads(json.dumps(self.template))
        changed["quote"] = "A different source clause"
        with self.assertRaisesRegex(ValueError, "exact source-bound proposal"):
            self.call(changed)


if __name__ == "__main__":
    unittest.main()
