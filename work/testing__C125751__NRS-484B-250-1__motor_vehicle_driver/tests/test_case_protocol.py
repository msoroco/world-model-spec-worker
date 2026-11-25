import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from case_protocol import load_case, validate_case, validate_comparison


def reviewed_fake(suffix):
    """A source-shaped CPU fixture, never a reviewed production source."""
    spec = copy.deepcopy(load_case(ROOT, suffix))
    for key in ('source_packet_sha256', 'map_sha256', 'crossing_id',
                'ego_route_sha256', 'other_route_sha256', 'ego_blueprint',
                'other_blueprint'):
        spec[key] = 'cpu-fixture-' + key
    return spec


class CaseProtocolTest(unittest.TestCase):
    def test_all_four_exact_specs_keep_original_review_gate(self):
        for suffix in ('precedence', 'advance', 'other_later', 'signal_red'):
            spec = load_case(ROOT, suffix)
            self.assertEqual(spec['source_status'], 'original_review_required')
            self.assertIsNone(spec['map_sha256'])
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, 'binding absent'):
                validate_case(spec, suffix)

    def test_declared_comparisons_isolate_one_request(self):
        left = reviewed_fake('precedence')
        for comparison, suffix in (('median_entry_order', 'other_later'),
                                   ('official_signal_readback', 'signal_red')):
            right = reviewed_fake(suffix)
            report = validate_comparison(left, right, comparison)
            self.assertTrue(report['measured_outcome_pending'])
            changed_fixed = copy.deepcopy(right)
            changed_fixed['camera_plan_sha256'] = 'different'
            with self.subTest(comparison=comparison), self.assertRaisesRegex(ValueError, 'fixed condition'):
                validate_comparison(left, changed_fixed, comparison)

    def test_authored_request_cannot_be_rewritten_as_measured_outcome(self):
        spec = reviewed_fake('precedence')
        spec['other_first'] = False
        with self.assertRaisesRegex(ValueError, 'declared variant'):
            validate_case(spec, 'precedence')
        spec = reviewed_fake('precedence')
        spec['source_status'] = 'reviewed'
        with self.assertRaisesRegex(ValueError, 'review boundary'):
            validate_case(spec, 'precedence')


if __name__ == '__main__':
    unittest.main()
