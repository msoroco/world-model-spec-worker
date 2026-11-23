import json
import unittest
from pathlib import Path
from runner import FRAMES, HZ, check, phase_at
from measure_episode import derive


class ExactCaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_full_duration_and_boundaries(self):
        receipt = check(self.config)
        self.assertEqual((receipt['frames'], receipt['rate_hz']), (600, 20))
        self.assertEqual([phase_at(self.config, frame)['name'] for frame in
                          (0, 159, 160, 319, 320, 439, 440, 599)],
                         ['approach', 'approach', 'acceleration', 'acceleration',
                          'peak', 'peak', 'departure', 'departure'])
        self.assertEqual(len([phase_at(self.config, frame) for frame in
                              range(FRAMES)]), FRAMES)

    def test_exact_identity_and_camera_rejection(self):
        changed = dict(self.config, case_id=self.config['case_id'] + '-wrong')
        with self.assertRaises(ValueError):
            check(changed)
        changed = dict(self.config, cameras=self.config['cameras'][:3])
        with self.assertRaises(ValueError):
            check(changed)
        changed = dict(self.config, spawn_point_index=8)
        with self.assertRaises(ValueError):
            check(changed)

    def test_short_or_truncated_phase_rejection(self):
        changed = dict(self.config, duration_s=10)
        with self.assertRaises(ValueError):
            check(changed)
        phases = [dict(phase) for phase in self.config['control_phases']]
        phases[-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(dict(self.config, control_phases=phases))

    def test_source_motion_join_and_negative(self):
        trace = [{'frame': i + 1000, 'video_frame': i, 'time_s': i / HZ,
                  'position_m': [i * .2, 0, 0],
                  'velocity_mps': [4 + i / 100, 0, 0],
                  'acceleration_mps2': [.2, 0, 0]} for i in range(FRAMES)]
        mapping = [{'video_frame': i, 'carla_frame': i + 1000,
                    'time_s': i / HZ} for i in range(FRAMES)]
        summary = derive(trace, mapping)
        self.assertEqual(summary['frames'], 600)
        self.assertAlmostEqual(summary['maximum_speed_mps'], 9.99)
        mapping[-1] = dict(mapping[-1], carla_frame=9999)
        with self.assertRaisesRegex(ValueError, 'join differs'):
            derive(trace, mapping)
