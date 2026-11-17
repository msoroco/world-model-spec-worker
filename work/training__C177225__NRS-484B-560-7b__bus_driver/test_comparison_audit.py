import copy
import unittest

from comparison_audit import audit_pair
from finalize_direction import signal_case_id
from native_scene import VIEWS


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        fixed = {'law_id': 'NRS-484B-560-7b', 'cell_id': 'C177225',
                 'actor': 'bus_driver', 'direction': 1, 'rate_hz': 20,
                 'duration_s': 30, 'frames': 600,
                 'cameras': list(VIEWS), 'rail_asset_blueprint': 'static.prop.ironplank',
                 'required_atoms': ['kin.velocity'], 'source_packets': [],
                 'weather': 'ClearNoon', 'authored_test_context': {}}
        self.reference_config = dict(fixed, case_id=signal_case_id('reference'))
        self.contrast_config = dict(fixed, case_id=signal_case_id('contrast'))
        signal = {'authorized': True, 'hand_signal': 'STOP',
                  'crossing_id': 'c177225_authored_rail_crossing',
                  'direction': 1, 'bus_id': 'bus-1', 'officer_id': 'officer-1'}
        self.reference_signal = dict(signal)
        self.contrast_signal = dict(signal, bus_id='bus-2', officer_id='officer-2')
        observation = {'native_frames': 600, 'saved_camera_sources': {
            name: {'sha256': 'source-' + name} for name in VIEWS},
            'saved_source_sha256': {str(i): str(i) for i in range(5)},
            'officer_direction_witnessed_frames': [10],
            'source_kind': 'synthetic_native_sample',
            'observed_complete_stop_before_line': True,
            'observed_crossing_entry': False}
        self.reference = dict(observation)
        self.contrast = dict(observation,
                             observed_complete_stop_before_line=False,
                             observed_crossing_entry=True)

    def audit(self):
        return audit_pair(self.reference, self.contrast,
                          self.reference_config, self.contrast_config,
                          self.reference_signal, self.contrast_signal)

    def test_fixed_pair_and_response_difference(self):
        result = self.audit()
        self.assertTrue(result['observed_response_difference'])
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertIsNone(result['legal_verdict'])

    def test_missing_source_or_fixed_context_change_rejected(self):
        self.contrast['saved_camera_sources'].pop('approach')
        with self.assertRaisesRegex(ValueError, 'complete saved source'):
            self.audit()
        self.contrast = copy.deepcopy(self.reference)
        self.contrast_config['weather'] = 'Rain'
        with self.assertRaisesRegex(ValueError, 'Fixed comparison'):
            self.audit()

    def test_direction_scope_and_unrealized_response(self):
        self.contrast_signal['crossing_id'] = 'other-crossing'
        with self.assertRaisesRegex(ValueError, 'recipient-bound'):
            self.audit()
        self.contrast_signal['crossing_id'] = 'c177225_authored_rail_crossing'
        self.contrast['observed_crossing_entry'] = False
        result = self.audit()
        self.assertEqual('response_not_established', result['status'])
        self.assertFalse(result['observed_response_difference'])


if __name__ == '__main__':
    unittest.main()
