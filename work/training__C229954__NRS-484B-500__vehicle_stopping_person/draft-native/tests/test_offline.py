import copy
import json
import unittest
from pathlib import Path

from runner import check, _source
from stop_controller import FRAMES, command


class DraftNativeContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_full_window_and_cameras(self):
        receipt = check(self.config)
        self.assertEqual((receipt['frames'], receipt['rate_hz']), (600, 20))
        self.assertEqual(receipt['source_views'],
                         ['overview', 'ego_front', 'curb_side', 'traffic_rear'])
        self.assertFalse(receipt['carla_contacted'])
        self.assertFalse(receipt['physical_completion'])
        self.assertEqual(FRAMES, 600)
        self.assertEqual(command(0, 10, 1)['phase'], 'approach')
        self.assertEqual(command(100, 0, 0)['phase'], 'hold')

    def test_no_missing_camera_or_short_window(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four named'):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['frames'] = 599
        with self.assertRaisesRegex(ValueError, '600-frame'):
            check(bad)

    def test_no_wrong_identity_or_outcome(self):
        for key, value in [('actor', 'motor_vehicle_driver'),
                           ('legal_verdict', 'compliant'),
                           ('physical_completion', True),
                           ('device_source_required', False)]:
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)

    def test_original_device_source_gate(self):
        path = Path('missing-device-source.json')
        with self.assertRaises(FileNotFoundError):
            _source(path)
        path.write_text('{}\n')
        try:
            with self.assertRaisesRegex(ValueError, 'Original official'):
                _source(path)
        finally:
            path.unlink()
