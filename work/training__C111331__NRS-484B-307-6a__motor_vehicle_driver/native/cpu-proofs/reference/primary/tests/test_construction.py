import copy
import json
from pathlib import Path
import unittest
import runner

class ExactRequestTests(unittest.TestCase):
    def test_exact_request(self):
        result = runner.check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['request_rows'], 480)
        self.assertFalse(result['carla_imported'])
        self.assertFalse(result['physical_success_claimed'])

    def test_request_corruption_rejected(self):
        path = Path('native-requests.jsonl')
        original = path.read_text()
        try:
            rows = [json.loads(line) for line in original.splitlines()]
            rows[200]['signal_phase_requested'] = 'green'
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                runner.check()
        finally:
            path.write_text(original)

    def test_observation_claim_rejected(self):
        path = Path('config.json')
        original = path.read_text()
        try:
            config = json.loads(original)
            config['no_native_or_original_observation_claimed'] = False
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'Physical evidence claimed'):
                runner.check()
        finally:
            path.write_text(original)

    def test_observed_tick_saved_handoff(self):
        sample = {'request_index': 7, 'native_frame': 107, 'time_s': .35,
                  'native_center_xy_m': [1.75, -8.5], 'native_z_m': .5,
                  'native_body_xy_m': [[1, -9], [2, -9], [2, -8], [1, -8]],
                  'native_yaw_deg': 90, 'speed_mps': 4.0}
        native, trace, video = runner.saved_capture_rows(sample, 7)
        self.assertEqual(native['source_kind'], 'original_native_observation')
        self.assertEqual(trace['frame'], video['native_frame'])
        self.assertEqual(trace['frame'], video['carla_frame'])
        self.assertEqual(trace['position_m'], [1.75, -8.5, .5])
        self.assertNotIn('source_kind', sample)
        with self.assertRaisesRegex(ValueError, 'frame or body differs'):
            runner.saved_capture_rows(sample, 8)

    def test_signal_camera_uses_authored_geometry(self):
        config = json.loads(Path('config.json').read_text())
        camera = runner.signal_camera_plan(config)
        self.assertEqual([camera['x'], camera['y']], config['camera_plan']['authored_xy_m'])
        self.assertGreater(camera['yaw_deg'], 0)
        self.assertLess(camera['yaw_deg'], 90)
        self.assertEqual(camera['horizontal_fov_deg'], config['camera_plan']['horizontal_fov_deg'])

    def test_four_original_camera_sources(self):
        config = json.loads(Path('config.json').read_text())
        plans = runner.original_camera_plans(config)
        self.assertEqual(set(plans), {'overview', 'approach', 'reference_corner', 'driver_reference'})
        self.assertEqual(plans['overview']['size'], (1920, 1080))
        self.assertTrue(all(plan['size'] == (1280, 720) for name, plan in plans.items() if name != 'overview'))
        self.assertEqual(plans['reference_corner']['fov_deg'], config['camera_plan']['horizontal_fov_deg'])
        self.assertEqual(plans['reference_corner']['y'], config['camera_plan']['authored_xy_m'][1])
        self.assertTrue(plans['driver_reference']['attach_to_ego'])

if __name__ == '__main__': unittest.main()
