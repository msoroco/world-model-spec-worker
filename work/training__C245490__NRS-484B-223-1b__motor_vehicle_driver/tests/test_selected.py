import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at

class SelectedConstruction(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_window_and_source_views(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(len(result['camera_views']), 4)
        self.assertEqual(len([phase_at(self.config, i) for i in range(FRAMES)]), 600)
        self.assertLess(self.config['check_frame'], 180)
        self.assertIsNone(result['legal_verdict'])

    def test_exact_case_controls(self):
        suffix = self.config['case_id'].split('__')[-1]
        self.assertEqual(self.config['signal_start_frame'] < 180,
                         suffix != 'signal_after_safe')
        self.assertEqual(self.config['target_vehicle_behind_m'] < 12,
                         suffix == 'signal_before_unsafe')
        self.assertEqual(self.config['check_action'] == 'skipped',
                         suffix == 'signal_before_no_check')
