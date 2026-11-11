"""Reject changed fixed conditions in the matched signal contrast."""
import copy
import sys
import unittest
from pathlib import Path

ASSIGNMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSIGNMENT))
from signal_advance_comparison_audit import compare_rows, fixed_config


class SignalAdvanceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.signalled = [{'frame': 38033 + i, 'time_s': (i + 1) / 20,
                           'ego': {'position_xy_m': [i / 4, 0]},
                           'oncoming': {'position_xy_m': [4, 0]},
                           'reciprocal': {'position_xy_m': [30, 0]},
                           'ego_heading_deg': 0 if i < 200 else -90,
                           'ego_left_indicator': 32 <= i < 201}
                          for i in range(900)]
        self.omitted = copy.deepcopy(self.signalled)
        for row in self.omitted:
            row['ego_left_indicator'] = False

    def test_only_indicator_differs(self):
        self.assertEqual(compare_rows(self.signalled, self.omitted), 169)

    def test_subject_motion_change_rejected(self):
        self.omitted[80]['ego']['position_xy_m'][0] += 0.5
        with self.assertRaisesRegex(ValueError, 'Fixed original field differs: ego'):
            compare_rows(self.signalled, self.omitted)

    def test_opposing_motion_change_rejected(self):
        self.omitted[180]['oncoming']['position_xy_m'][0] += 0.5
        with self.assertRaisesRegex(ValueError, 'Fixed original field differs: oncoming'):
            compare_rows(self.signalled, self.omitted)

    def test_omitted_indicator_change_rejected(self):
        self.omitted[80]['ego_left_indicator'] = True
        with self.assertRaisesRegex(ValueError, 'Omitted branch has left indicator'):
            compare_rows(self.signalled, self.omitted)

    def test_missing_signalled_indicator_rejected(self):
        for row in self.signalled:
            row['ego_left_indicator'] = False
        with self.assertRaisesRegex(ValueError, 'Signalled branch contains no observed'):
            compare_rows(self.signalled, self.omitted)

    def test_configuration_normalization_keeps_motion_knobs(self):
        left = {'selected_case_id': 'a', 'left_signal_enabled': True,
                'case': {'selected_case_id': 'a', 'approach_speed_mps': 5}}
        right = {'selected_case_id': 'b', 'left_signal_enabled': False,
                 'case': {'selected_case_id': 'b', 'approach_speed_mps': 5}}
        self.assertEqual(fixed_config(left), fixed_config(right))
        right['case']['approach_speed_mps'] = 4
        self.assertNotEqual(fixed_config(left), fixed_config(right))


if __name__ == '__main__':
    unittest.main()
