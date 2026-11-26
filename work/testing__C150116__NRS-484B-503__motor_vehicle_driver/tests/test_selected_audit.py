"""Selected diagnostic receipt and four-comparison integrity tests."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from selected_audit import audit_selected


def inputs():
    return (json.loads((HERE / 'execution-manifest.json').read_text()),
            json.loads((HERE / 'case-plan.json').read_text()))


class SelectedAuditTests(unittest.TestCase):
    def test_sixteen_selected_receipts_four_comparisons_and_three_sweeps(self):
        result = audit_selected()
        self.assertEqual(len(result['cases']), 16)
        self.assertEqual(len(result['comparisons']), 4)
        self.assertEqual(len(result['sweep_audits']), 3)
        self.assertFalse(result['original_source_verified'])
        self.assertFalse(result['physical_acceptance'])

    def test_changed_construction_digest_rejected(self):
        manifest, plan = inputs()
        manifest['cases'][0]['construction_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'stale proof'):
            audit_selected(manifest, plan)

    def test_changed_selected_compatibility_rejected(self):
        manifest, plan = inputs()
        manifest['cases'][0]['compatibility']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'stale proof'):
            audit_selected(manifest, plan)

    def test_changed_physical_binding_rejected(self):
        manifest, plan = inputs()
        manifest['cases'][0]['physical_preparation']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'stale proof'):
            audit_selected(manifest, plan)

    def test_missing_case_rejected(self):
        manifest, plan = inputs()
        manifest['cases'].pop()
        with self.assertRaisesRegex(ValueError, 'all selected cases'):
            audit_selected(manifest, plan)

    def test_missing_comparison_rejected(self):
        manifest, plan = inputs()
        plan['comparisons'].pop()
        with self.assertRaisesRegex(ValueError, 'four planned comparisons'):
            audit_selected(manifest, plan)

    def test_missing_declared_difference_rejected(self):
        manifest, plan = inputs()
        plan['comparisons'][0]['case_ids'][1] = plan['comparisons'][0]['case_ids'][0]
        with self.assertRaisesRegex(ValueError, 'comparison case identity'):
            audit_selected(manifest, plan)

    def test_changed_fixed_condition_rejected(self):
        manifest, plan = inputs()
        plan['comparisons'][0]['case_ids'][0] = plan['comparisons'][1]['case_ids'][1]
        with self.assertRaisesRegex(ValueError, 'fixed diagnostic variable'):
            audit_selected(manifest, plan)


if __name__ == '__main__':
    unittest.main()
