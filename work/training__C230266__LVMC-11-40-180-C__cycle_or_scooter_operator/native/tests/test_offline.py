import json
import unittest
from pathlib import Path
from runner import RiderPolicy, check

HERE = Path(__file__).resolve().parent.parent


class SidewalkOffline(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((HERE/'config.json').read_text())

    def test_full_duration_and_sidewalk(self):
        summary = check(self.config)
        self.assertEqual(summary['frames'], 600)
        self.assertEqual(summary['sidewalk_lane_id'], -2)
        self.assertEqual(len(summary['cameras']), 4)
        self.assertFalse(summary['native_imported'])

    def test_signal_request_timing(self):
        policy = RiderPolicy(self.config)
        requested = [i for i in range(600) if policy.request(i)['audible_signal_request']]
        self.assertEqual(requested, [] if self.config['signal_frame'] is None else [self.config['signal_frame']])
        self.assertEqual(policy.request(90)['forward_speed_mps'],
                         0 if self.config['pause_window_frames'] == [80, 110] else 1.4)
        self.assertEqual(policy.request(120)['forward_speed_mps'], 1.4)

    def test_missing_microphone_rejected(self):
        modified = dict(self.config)
        modified['pedestrian_microphone'] = {'location': 'rider_actor'}
        with self.assertRaisesRegex(ValueError, 'pedestrian location'):
            check(modified)

    def test_wrong_camera_rejected(self):
        modified = dict(self.config)
        modified['cameras'] = self.config['cameras'][:3]
        with self.assertRaisesRegex(ValueError, 'Four original'):
            check(modified)


if __name__ == '__main__':
    unittest.main()
