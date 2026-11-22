import json
import unittest
from pathlib import Path
import runner
from candidate_tuning import tuning

class BundleTest(unittest.TestCase):
    def test_exact_primary_contract(self):
        checked=runner.check()
        config=json.loads((Path(__file__).parents[1]/'config.json').read_text())
        self.assertEqual(checked['case_id'],config['case_id'])
        self.assertEqual(checked['frames'],600)
        self.assertFalse(checked['physical_acceptance_claimed'])
    def test_risk_candidate_is_source_specified(self):
        self.assertIsNotNone(tuning('fallback1').risk_trigger)
        with self.assertRaises(ValueError):
            tuning('unknown')
