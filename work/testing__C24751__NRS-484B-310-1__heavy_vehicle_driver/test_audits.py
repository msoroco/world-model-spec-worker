"""Independent original-source rejection and comparison isolation checks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import comparison_audit
import delivery_audit
from flashing_red_native import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c24751/audit-test'


class AuditTest(unittest.TestCase):
    def test_original_attempt_required(self):
        with self.assertRaisesRegex(ValueError, 'original attempt missing'):
            delivery_audit.audit_attempt(SCRATCH / 'no-original',
                                         SCRATCH / 'no-result.json',
                                         ASSIGNMENT + '__crosswalk_stop')

    def test_seal_required_before_any_audit(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            result = root / 'result.json'
            result.write_text(json.dumps({'case_id': ASSIGNMENT + '__crosswalk_stop',
                'diagnostic_fixture': False, 'physical_acceptance_claimed': False,
                'legal_verdict_claimed': False}) + '\n')
            with self.assertRaisesRegex(ValueError, 'capture-seal.json'):
                delivery_audit.audit_attempt(root, result,
                                             ASSIGNMENT + '__crosswalk_stop')

    def test_comparison_requires_every_exact_case(self):
        with self.assertRaisesRegex(ValueError, 'every exact case'):
            comparison_audit.audit_comparison('crosswalk_stop_location', {})

    def test_crosswalk_comparison_isolates_original_stop_position(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            pairs = {}
            for index, name in enumerate(('crosswalk_stop', 'crosswalk_late_stop')):
                case_id = ASSIGNMENT + '__' + name
                item = {'format': 'c24751-original-delivery-audit-v1',
                    'case_id': case_id, 'original_frame_count': 900,
                    'flashing_red_transitions': 12,
                    'legal_status': 'unresolved',
                    'post_stop_right_to_proceed': 'unresolved_applicable_rules',
                    'source_sha256': {'capture-seal.json': 'source-seal-' + name},
                    'reference_kind': 'crosswalk', 'surveyed_reference_m': 20.0,
                    'stop_geometry_sha256': 'same-survey', 'map_sha256': 'same-map',
                    'signal_identity_sha256': 'same-signal',
                    'occluder_identity_sha256': 'same-occluder',
                    'stop_observations': [{'front_m': 18.8 if index == 0 else 20.8}]}
                path = root / (name + '.json')
                path.write_text(json.dumps(item) + '\n')
                pairs[case_id] = path
            checked = comparison_audit.audit_comparison('crosswalk_stop_location', pairs)
            self.assertEqual(checked['legal_status'], 'unresolved')
            second = root / 'crosswalk_late_stop.json'
            changed = json.loads(second.read_text())
            changed['signal_identity_sha256'] = 'different-signal'
            second.write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'fixed physical signal'):
                comparison_audit.audit_comparison('crosswalk_stop_location', pairs)

    def test_case_audit_protocol_preserves_post_stop_uncertainty(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            result = root / 'result.json'
            case_id = ASSIGNMENT + '__crosswalk_stop'
            result.write_text(json.dumps({'case_id': case_id,
                'diagnostic_fixture': False, 'physical_acceptance_claimed': False,
                'legal_verdict_claimed': False}) + '\n')
            site = {'map_sha256': 'map', 'signal_identity_sha256': 'signal',
                    'occluder_identity_sha256': 'occluder',
                    'stop_geometry_sha256': 'stop'}
            source = {'capture-seal.json': 'seal'}
            observation = {'stop_observations': [{'frame': 100, 'front_m': 18.8,
                                                 'before_reference': True}],
                           'flashing_red_transitions': 4,
                           'surveyed_reference_m': 20.0}
            decoded = lambda path, size: {'decoded_frames': 900,
                                           'width': size[0], 'height': size[1]}
            with patch.object(delivery_audit, 'original', return_value=(site, source)), \
                 patch.object(delivery_audit, 'rows', return_value=[{}] * 900), \
                 patch.object(delivery_audit, 'check_joins'), \
                 patch.object(delivery_audit, 'measure_original', return_value=observation), \
                 patch.object(delivery_audit, 'required', return_value=result):
                audited = delivery_audit.audit_attempt(root, result, case_id, decoded)
            self.assertEqual(audited['original_frame_count'], 900)
            self.assertEqual(audited['flashing_red_transitions'], 4)
            self.assertEqual(audited['post_stop_right_to_proceed'],
                             'unresolved_applicable_rules')


if __name__ == '__main__':
    unittest.main()
