import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit_comparisons', ROOT / 'audit_comparisons.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class ComparisonAuditTests(unittest.TestCase):
    def test_all_declared_comparisons_use_bound_source_proofs(self):
        report = audit_module.audit()
        self.assertEqual(len(report['cases']), 5)
        self.assertEqual(len(report['comparisons']), 4)
        self.assertFalse(report['physical_acceptance_claimed'])
        self.assertFalse(report['legal_acceptance_claimed'])

    def test_missing_source_proof_is_rejected(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        manifest['cases'][-1]['compatibility']['receipt'] = 'missing-receipt.json'
        with self.assertRaisesRegex(ValueError, 'Missing or changed source proof'):
            audit_module.audit(plan=plan, manifest=manifest)

    def test_fixed_condition_and_deliberate_difference_failures(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        cases = {entry['case_id'].split('__')[-1]: audit_module.load_case(entry)
                 for entry in manifest['cases']}
        left = cases['off_ego_left_near_time']
        opposite = copy.deepcopy(cases['off_opposite_left_turn'])
        opposite['config']['site']['crossing_id'] = 999
        with self.assertRaisesRegex(ValueError, 'fixed crossing'):
            audit_module.audit_pair('opposite_left_turn_exception_context', left, opposite)
        opposite = copy.deepcopy(cases['off_opposite_left_turn'])
        opposite['measured']['opposite_left_turn_context']['original_negative_steering_observed'] = False
        with self.assertRaisesRegex(ValueError, 'left turn missing'):
            audit_module.audit_pair('opposite_left_turn_exception_context', left, opposite)


if __name__ == '__main__':
    unittest.main()
