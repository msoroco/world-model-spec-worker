"""Comparison logic tests use invented reports only to verify rejection logic."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import AID, PAIRS, audit_comparisons


def reports():
    values = {
        'aisle_full_park': ('aisle_full', 'park', 8, 0),
        'aisle_partial_park': ('aisle_partial', 'park', 2, 0),
        'adjacent_space_park': ('adjacent_space', 'park', 0, 0),
        'aisle_loading_stop': ('aisle_full', 'loading_stop', 8, 0),
        'aisle_travel': ('aisle_full', 'travel', 8, 1),
    }
    result = {}
    for suffix, (footprint, activity, overlap, speed) in values.items():
        case_id = AID + '__' + suffix
        result[case_id] = {'format': 'worker-delivery-audit', 'passed': True,
                           'protocol_fixture_checked': False, 'case_id': case_id,
                           'frame_count': 900, 'physical_acceptance_claimed': True,
                           'comparison_record': {'source_kind': 'original_native_capture',
                              'fixed_source_sha256': {'map': 'fixture-source'},
                              'camera_plan': [{'name': 'overview'}], 'duration_s': 45,
                              'requested_footprint': footprint, 'requested_activity': activity,
                              'measurement': {'frame_count': 900,
                                              'terminal_mean_aisle_body_overlap_m2': overlap,
                                              'terminal_max_speed_mps': speed}}}
    return result


class ComparisonTests(unittest.TestCase):
    def test_four_controlled_comparisons(self):
        self.assertEqual([row['comparison_id'] for row in audit_comparisons(reports())], list(PAIRS))

    def test_reject_synthetic_or_changed_fixed_source(self):
        data = reports()
        data[AID + '__aisle_partial_park']['passed'] = False
        with self.assertRaisesRegex(ValueError, 'original accepted report'):
            audit_comparisons(data)
        data = reports()
        data[AID + '__aisle_partial_park']['comparison_record']['fixed_source_sha256']['map'] = 'other'
        with self.assertRaisesRegex(ValueError, 'changed fixed original condition'):
            audit_comparisons(data)

    def test_reject_unrealized_body_or_activity_difference(self):
        data = reports()
        data[AID + '__aisle_partial_park']['comparison_record']['measurement']['terminal_mean_aisle_body_overlap_m2'] = 8
        with self.assertRaisesRegex(ValueError, 'full/partial body'):
            audit_comparisons(data)
        data = reports()
        data[AID + '__aisle_travel']['comparison_record']['measurement']['terminal_max_speed_mps'] = 0
        with self.assertRaisesRegex(ValueError, 'park/travel'):
            audit_comparisons(data)


if __name__ == '__main__':
    unittest.main()
