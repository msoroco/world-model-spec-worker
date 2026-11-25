"""Mock-only tests of independent original-attempt rejection and comparisons."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location('c228302_delivery_audit', HERE / 'delivery_audit.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DeliveryAuditTests(unittest.TestCase):
    def reports(self):
        plan = json.loads((HERE / 'case-plan.json').read_text())
        reports = {}
        fixed = {key: 'fixed_source_hash' for key in
                 ('map_sha256', 'site_sha256', 'camera_plan_sha256',
                  'exit_route_sha256', 'approach_route_sha256', 'blueprints_sha256')}
        for row in plan['cases']:
            design = row['construction']
            cid = row['case_id']
            reports[cid] = {
                'format': 'c228302-independent-original-audit-v1',
                'case_id': cid, 'source_kind': 'original_native_capture',
                'legal_status': 'unresolved', 'physical_acceptance': False,
                'comparison_record': {'case_id': cid, 'frame_count': 900,
                                      'original_history_sha256': 'mock_source_' + cid,
                                      **fixed, 'policy': design['policy'],
                                      'approaching_count': design['approaching_count'],
                                      'approach_headway_s': design['approach_headway_s']}}
        return reports

    def test_all_four_mock_comparison_contracts(self):
        self.assertEqual(len(MODULE.audit_comparisons(self.reports())), 4)

    def test_changed_fixed_source_rejected(self):
        reports = self.reports()
        last = list(reports)[-1]
        reports[last]['comparison_record']['map_sha256'] = 'different_map'
        with self.assertRaisesRegex(ValueError, 'fixed comparison condition changed'):
            MODULE.audit_comparisons(reports)

    def test_changed_undeclared_variable_rejected(self):
        reports = self.reports()
        second = list(reports)[1]
        reports[second]['comparison_record']['approach_headway_s'] = 4.0
        with self.assertRaisesRegex(ValueError, 'undeclared difference'):
            MODULE.audit_comparisons(reports)

    def test_missing_original_attempt_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'original attempt missing'):
                MODULE.audit_attempt(Path(temporary) / 'absent', list(self.reports())[0])

    def test_synthetic_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'source-manifest.json').write_text(json.dumps({
                'case_id': list(self.reports())[0],
                'source_kind': 'synthetic_diagnostic_fixture',
                'diagnostic_fixture': True, 'reviewer': 'mock'}))
            with self.assertRaisesRegex(ValueError, 'reviewed original source identity missing'):
                MODULE.audit_attempt(root, list(self.reports())[0])
