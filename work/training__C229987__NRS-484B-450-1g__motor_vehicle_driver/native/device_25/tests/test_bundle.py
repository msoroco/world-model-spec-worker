import json
import unittest
from pathlib import Path
import road
import runner

class BundleTest(unittest.TestCase):
    def test_signal_actor_contract_and_exact_target(self):
        self.assertTrue(road.check()['signal_specified'])
        self.assertTrue(runner.check()['passed'])
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['selected_case_id'], config['case_id'])
        self.assertIn(config['requested_front_gap_ft'], (25.0, 30.0, 35.0))
        self.assertEqual(len(config['cameras']), 4)

    def test_missing_case_rejected(self):
        self.assertNotIn('40', runner.TARGETS_FT)
