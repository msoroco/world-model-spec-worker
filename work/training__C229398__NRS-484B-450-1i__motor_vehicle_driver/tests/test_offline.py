import copy
import json
import unittest
from pathlib import Path
from runner import check

class RailCaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())
    def test_exact_request(self):
        self.assertEqual(check(self.config)['frames'], 600)
    def test_missing_camera(self):
        wrong = copy.deepcopy(self.config); wrong['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four exact'):
            check(wrong)
    def test_changed_rail_gap(self):
        wrong = copy.deepcopy(self.config); wrong['target_footprint_gap_m'] = 14.5
        with self.assertRaisesRegex(ValueError, 'target changed'):
            check(wrong)
    def test_claimed_physical_result(self):
        wrong = copy.deepcopy(self.config); wrong['physical_verified'] = True
        with self.assertRaisesRegex(ValueError, 'claims an outcome'):
            check(wrong)
