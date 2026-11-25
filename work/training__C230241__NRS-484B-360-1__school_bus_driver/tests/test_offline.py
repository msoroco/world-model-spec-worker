import copy
import json
import unittest
from pathlib import Path
from runner import check, FRAMES, RATE
from controller import control


class DraftContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_full_source_capture(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(FRAMES, 600)
        self.assertEqual(RATE, 20)
        self.assertFalse(result['pupils_aboard_observed'])
        self.assertFalse(result['legal_verdict_claimed'])

    def test_reject_camera_or_pupil_claim(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['pupils_aboard_observed'] = True
        with self.assertRaises(ValueError):
            check(bad)

    def test_speed_feedback_is_request_only(self):
        suffix = self.config['case_id'].rsplit('__', 1)[-1]
        request = control(suffix, [0, 0, 0])
        self.assertEqual(request['measurement_source'], 'post_tick_original_velocity')
        self.assertGreater(request['requested_speed_mps'], 0)
        self.assertIsNone(self.config['legal_verdict'])

    def test_reject_short_capture(self):
        bad = copy.deepcopy(self.config)
        bad['duration_s'] = 29
        with self.assertRaises(ValueError):
            check(bad)
