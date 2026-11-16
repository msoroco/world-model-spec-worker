"""Reject changed fixed conditions in the matched signal contrast."""
import copy
import json
import sys
import unittest
from pathlib import Path

ASSIGNMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSIGNMENT))
from signal_advance_comparison_audit import compare_rows, fixed_config
from prove_signal_distance_comparison import compare_fixed_motion, compare_fixed_construction, CASES


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

    def test_three_distance_sources_reject_changed_opposing_motion(self):
        third = copy.deepcopy(self.signalled)
        compare_fixed_motion((self.signalled, self.omitted, third))
        third[380]['oncoming']['position_xy_m'][0] += 0.5
        with self.assertRaisesRegex(ValueError, 'non-signal source condition changed'):
            compare_fixed_motion((self.signalled, self.omitted, third))

    def test_three_selected_constructions_reject_undeclared_change(self):
        manifest = json.loads((ASSIGNMENT / 'execution-manifest.json').read_text())
        bundles = []
        for name in CASES:
            case = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + name))
            bundle = json.loads((ASSIGNMENT / case['construction']).read_text())
            bundles.append({file['path']: file['content'] for file in bundle['files']})
        compare_fixed_construction(bundles)
        tampered = copy.deepcopy(bundles)
        tampered[0]['camera_setup.py'] += '\n# undeclared camera change\n'
        with self.assertRaisesRegex(ValueError, 'Construction differs outside declared signal target'):
            compare_fixed_construction(tampered)
        tampered = copy.deepcopy(bundles)
        config = json.loads(tampered[2]['config.json'])
        config['duration_s'] = 44
        tampered[2]['config.json'] = json.dumps(config)
        with self.assertRaisesRegex(ValueError, 'Construction differs outside declared signal target'):
            compare_fixed_construction(tampered)


if __name__ == '__main__':
    unittest.main()
