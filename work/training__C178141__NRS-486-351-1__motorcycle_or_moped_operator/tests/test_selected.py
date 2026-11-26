"""Exercise selected Native route, mode and fallback controller contracts."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'native'))
from geometry import check as geometry_check
from route import compare_requested_routes
from runner import check, control


class Subject:
    def get_transform(self):
        return type('Transform', (), {'location': type('Location', (), {'y': 0.0})()})()

    def get_velocity(self):
        return type('Velocity', (), {'x': 0.0, 'y': 0.0})()


def config(suffix, candidate='primary'):
    path = HERE / 'draft-exact' / suffix / candidate / 'construction.json'
    construction = json.loads(path.read_text())
    return json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))


class SelectedNative(unittest.TestCase):
    def test_lane_route_and_mode_matrix(self):
        self.assertEqual(geometry_check()['lane_ids'], [-1, -2])
        self.assertEqual(compare_requested_routes()['only_requested_difference'], 'lateral_position_m')
        expected = [('beside', 'stationary', 'motorcycle', False),
                    ('between', 'stationary', 'motorcycle', False),
                    ('between', 'moving', 'motorcycle', False),
                    ('between', 'stationary', 'moped', False),
                    ('between', 'stationary', 'motorcycle', True)]
        for number, row in enumerate(expected, 1):
            cfg = config(f'probe_{number}')
            self.assertEqual(check(cfg)['frames'], 600)
            self.assertEqual(tuple(cfg[k] for k in ('split_case', 'surrounding_mode',
                'machine_candidate', 'police_duty_requested')), row)
            self.assertEqual([camera['name'] for camera in cfg['cameras']],
                ['overview', 'approach', 'reference_corner', 'driver_reference'])

    def test_fallback_changes_only_common_feedback_gain(self):
        for number in range(1, 6):
            primary = config(f'probe_{number}')
            fallback = config(f'probe_{number}', 'fallback1')
            self.assertEqual(primary['steer_gain'], .1)
            self.assertEqual(fallback['steer_gain'], .07)
            for key in primary:
                if key not in ('steer_gain', 'candidate_id'):
                    self.assertEqual(primary[key], fallback[key])
            self.assertGreater(control(primary, 0, Subject())['steer'],
                               control(fallback, 0, Subject())['steer'])

    def test_invalid_assignment_mode_rejected(self):
        cfg = config('probe_1')
        cfg['surrounding_mode'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'mode declaration'):
            check(cfg)


if __name__ == '__main__':
    unittest.main()
