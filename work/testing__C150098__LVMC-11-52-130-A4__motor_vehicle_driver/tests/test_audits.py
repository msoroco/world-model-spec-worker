"""Independent audit source gates and exact comparison invariants."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import comparison_audit
import delivery_audit
from hydrant import ASSIGNMENT


class AuditTest(unittest.TestCase):
    def test_original_attempt_required(self):
        with self.assertRaisesRegex(ValueError, 'original attempt missing'):
            delivery_audit.audit_attempt(
                ROOT / '.runtime-work/c150098/no-original',
                ROOT / '.runtime-work/c150098/no-result.json',
                ASSIGNMENT + '__upstream_inside')

    def test_case_audit_requires_full_original_inputs(self):
        scratch = ROOT / '.runtime-work/c150098/audit-test'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            result = root / 'result.json'
            result.write_text(json.dumps({'case_id': ASSIGNMENT + '__upstream_inside',
                'diagnostic_fixture': False, 'physical_acceptance_claimed': False,
                'legal_verdict_claimed': False}) + '\n')
            with self.assertRaisesRegex(ValueError, 'capture-seal.json'):
                delivery_audit.audit_attempt(root, result,
                                             ASSIGNMENT + '__upstream_inside')

    def test_comparison_requires_every_exact_case(self):
        with self.assertRaisesRegex(ValueError, 'every exact case'):
            comparison_audit.audit_comparison(
                'upstream_parallel_15ft_boundary', {})

    def test_original_case_audit_protocol(self):
        scratch = ROOT / '.runtime-work/c150098/audit-test'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            result = root / 'result.json'
            case_id = ASSIGNMENT + '__upstream_inside'
            result.write_text(json.dumps({'case_id': case_id,
                'diagnostic_fixture': False, 'physical_acceptance_claimed': False,
                'legal_verdict_claimed': False}) + '\n')
            site = {'map_sha256': 'map', 'hydrant_identity_sha256': 'hydrant',
                'parallel_parking_authority_sha256': 'authority'}
            source = {'capture-seal.json': 'seal'}
            observation = {'target_frame_count': 900,
                           'minimum_longitudinal_gap_m': 4.422}
            decoded = lambda path, size: {'decoded_frames': 900,
                'width': size[0], 'height': size[1]}
            with patch.object(delivery_audit, 'original', return_value=(site, source)), \
                 patch.object(delivery_audit, 'rows', return_value=[{}] * 900), \
                 patch.object(delivery_audit, 'check_joins'), \
                 patch.object(delivery_audit, 'measure_original_history',
                              return_value=observation), \
                 patch.object(delivery_audit, 'required', return_value=result):
                audited = delivery_audit.audit_attempt(root, result, case_id, decoded)
            self.assertEqual(audited['original_frame_count'], 900)
            self.assertEqual(audited['minimum_target_side_gap_m'], 4.422)
            self.assertEqual(audited['legal_status'], 'unresolved')


if __name__ == '__main__':
    unittest.main()
