import json
import unittest
from pathlib import Path
import road
import runner

class BundleTest(unittest.TestCase):
    def test_corridor_and_exact_case(self):
        self.assertEqual(road.check()['clear_corridor_m'], 1800.0)
        self.assertTrue(runner.check()['passed'])
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['selected_case_id'], config['case_id'])
        self.assertIn(config['requested_speed_mph'], (75.0, 80.0, 85.0))

    def test_missing_case_rejected(self):
        self.assertNotIn('probe_04', runner.TARGETS_MPH)
