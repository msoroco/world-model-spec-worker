import copy
import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at


class CaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_full_source_window(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(result['source_views'],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertFalse(result['physical_visibility_verified'])
        self.assertEqual([phase_at(self.config, i)['name'] for i in
                          (0, 399, 400, 499, 500, 599)],
                         ['travel', 'travel', 'braking', 'braking', 'hold', 'hold'])
        self.assertEqual((FRAMES, RATE), (600, 20))
        with self.assertRaises(ValueError):
            phase_at(self.config, 600)

    def test_missing_camera_and_window_rejected(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['control_phases'][-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(bad)

    def test_wrong_actor_and_lamp_request_rejected(self):
        bad = copy.deepcopy(self.config)
        bad['actor'] = 'motor_vehicle_driver'
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['requested_light_state'] = 'Off'
        with self.assertRaises(ValueError):
            check(bad)

    def test_no_fabricated_physical_outcome(self):
        bad = copy.deepcopy(self.config)
        bad['physical_visibility_verified'] = True
        with self.assertRaises(ValueError):
            check(bad)
