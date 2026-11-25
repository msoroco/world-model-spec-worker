import json
from pathlib import Path
import unittest
from runner import check
from live_capture import requested_speed, START_Y

class ExactCase(unittest.TestCase):
    def test_identity_and_geometry(self):
        config=json.loads(Path('config.json').read_text())
        self.assertTrue(check(config)['passed'])
        self.assertEqual(config['case_id'], config['selected_case_id'])
        self.assertLess(START_Y,-40)
    def test_control_is_request(self):
        case=json.loads(Path('config.json').read_text())['case_id']
        expected=0 if case.endswith('probe_1') else 4
        self.assertEqual(requested_speed(140,case,-18),expected)
        with self.assertRaises(ValueError):requested_speed(600,case,-18)

if __name__=='__main__':unittest.main()
