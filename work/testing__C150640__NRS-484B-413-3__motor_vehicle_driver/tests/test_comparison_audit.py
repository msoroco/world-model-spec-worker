"""Comparison fixtures verify original-only and measured contrast rejection."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import AID, PAIRS, audit_pair


def reports():
    values = {
        'stop_signal_before': ('stop', 'before', True, True, 0, 'driver-present'),
        'stop_signal_after': ('stop', 'after', True, False, 0, 'driver-present'),
        'decrease_signal_before': ('sudden_decrease', 'before', True, True, 4, 'driver-present'),
        'decrease_signal_after': ('sudden_decrease', 'after', True, False, 4, 'driver-present'),
        'stop_no_rear_driver': ('stop', 'before', False, True, 0, 'driver-absent')}
    result = {}
    for suffix, (maneuver, signal, driver, precedes, speed, driver_source) in values.items():
        case_id = AID + '__' + suffix
        result[case_id] = {'format': 'worker-delivery-audit', 'passed': True,
                           'protocol_fixture_checked': False, 'case_id': case_id,
                           'frame_count': 900, 'physical_acceptance_claimed': True,
                           'comparison_record': {'source_kind': 'original_native_capture',
                              'fixed_source_sha256': {'map': 'fixture-source'},
                              'rear_driver_source_sha256': driver_source,
                              'camera_plan': [{'name': 'overview'}], 'duration_s': 45,
                              'requested_maneuver': maneuver,
                              'requested_signal_policy': signal,
                              'requested_rear_driver_present': driver,
                              'measurement': {'frame_count': 900,
                                              'signal_onset_frame': 110 if precedes else 210,
                                              'event_onset_frame': 200,
                                              'signal_precedes_event': precedes,
                                              'rear_driver_present': driver,
                                              'terminal_max_speed_mps': speed,
                                              'event_speed_drop_mps': 4,
                                              'rear_gap_at_event_m': 8}}}
    return result


class ComparisonTests(unittest.TestCase):
    def test_four_controlled_comparisons(self):
        data = reports()
        self.assertEqual([audit_pair(name, data)['comparison_id'] for name in PAIRS], list(PAIRS))

    def test_reject_synthetic_or_changed_fixed_source(self):
        data = reports()
        data[AID + '__stop_signal_after']['passed'] = False
        with self.assertRaisesRegex(ValueError, 'original accepted report'):
            audit_pair('stop_signal_order', data)
        data = reports()
        data[AID + '__stop_signal_after']['comparison_record']['fixed_source_sha256']['map'] = 'other'
        with self.assertRaisesRegex(ValueError, 'changed fixed original condition'):
            audit_pair('stop_signal_order', data)

    def test_reject_unrealized_signal_motion_or_driver_difference(self):
        data = reports()
        data[AID + '__stop_signal_after']['comparison_record']['measurement']['signal_precedes_event'] = True
        with self.assertRaisesRegex(ValueError, 'signal onset order'):
            audit_pair('stop_signal_order', data)
        data = reports()
        data[AID + '__decrease_signal_before']['comparison_record']['measurement']['terminal_max_speed_mps'] = 0
        with self.assertRaisesRegex(ValueError, 'stop/decrease'):
            audit_pair('stop_vs_decrease', data)
        data = reports()
        data[AID + '__stop_no_rear_driver']['comparison_record']['measurement']['rear_driver_present'] = True
        with self.assertRaisesRegex(ValueError, 'rear-driver presence'):
            audit_pair('rear_driver_presence', data)


if __name__ == '__main__':
    unittest.main()
