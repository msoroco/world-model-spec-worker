import copy
import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at


class CaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_complete_source_window(self):
        receipt = check(self.config)
        self.assertEqual((receipt['frames'], receipt['rate_hz']), (600, 20))
        self.assertFalse(receipt['attention_observed'])
        self.assertEqual([phase_at(self.config, i)['name'] for i in
                          (0, 199, 200, 479, 480, 599)],
                         ['approach', 'approach', 'travel', 'travel',
                          'departure', 'departure'])
        self.assertEqual(len([phase_at(self.config, i) for i in range(FRAMES)]), FRAMES)
        with self.assertRaises(ValueError):
            phase_at(self.config, FRAMES)

    def test_reject_missing_camera_and_short_window(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['control_phases'][-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(bad)

    def test_reject_invented_attention(self):
        bad = copy.deepcopy(self.config)
        bad['driver_attention_to_operation'] = True
        with self.assertRaises(ValueError):
            check(bad)

    def test_source_files_present(self):
        self.assertTrue(Path('attention_observation.py').is_file())
        self.assertEqual(RATE, 20)
