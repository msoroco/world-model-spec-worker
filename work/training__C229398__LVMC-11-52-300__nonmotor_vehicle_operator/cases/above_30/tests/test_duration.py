import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check, request

class TestDuration(unittest.TestCase):
    def test_exact_request(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        self.assertTrue(check()['passed'])
        self.assertEqual(request(cfg['parking_stop_frame'] - 1, cfg)['phase'], 'approach')
        self.assertEqual(request(cfg['parking_stop_frame'], cfg)['phase'], 'parking_request')
        self.assertEqual(request(cfg['capture_frames'] - 1, cfg)['requested_stationary_duration_s'], cfg['requested_stationary_duration_s'])
