import json
from pathlib import Path
import unittest

from layout import check as layout_check
from runner import CAMERAS, FRAMES, check, is_early, is_stop, requested_speed


class NativeTimingTest(unittest.TestCase):
    def test_cpu_only_identity_and_camera_profile(self):
        self.assertTrue(check()['passed'])
        self.assertEqual(FRAMES, 600)
        self.assertEqual([x[0] for x in CAMERAS],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertEqual(layout_check()['lane_id'], -1)

    def test_action_and_signal_controls(self):
        config = json.loads(Path('config.json').read_text())
        suffix = config['case_suffix']
        self.assertEqual(config['signal_command_frame'],
                         100 if is_early(suffix) else 160 if is_stop(suffix) else 121)
        self.assertEqual(requested_speed(suffix, 119), 8.0)
        self.assertEqual(requested_speed(suffix, 200), 0.0 if is_stop(suffix) else 4.0)


if __name__ == '__main__':
    unittest.main()
