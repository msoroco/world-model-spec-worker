"""CPU construction checks; no CARLA connection or legal conclusion."""
import json
from pathlib import Path
import unittest

import road
import runner
from speed_measure import measure


class SelectedSpeedTest(unittest.TestCase):
    def test_authored_sign_and_capture(self):
        self.assertEqual(road.check()['posted_corridor_m'], 1800.0)
        check = runner.check()
        self.assertTrue(check['passed'])
        self.assertEqual(check['frames'], 600)
        self.assertEqual(check['cameras'], ['overview', 'approach', 'reference_corner', 'driver_reference'])

    def test_exact_selected_config(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['selected_case_id'], config['case']['case_id'])
        self.assertEqual(config['posted_speed_request_mph'], 30)
        self.assertIn(config['requested_speed_mph'], (25.0, 30.0, 35.0))

    def test_missing_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing required source'):
            measure(Path('missing-original'))


if __name__ == '__main__':
    unittest.main()
