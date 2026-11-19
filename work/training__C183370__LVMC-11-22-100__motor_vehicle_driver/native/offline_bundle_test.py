"""Materialized exact-case CPU checks; does not contact a CARLA server."""
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'native'))
import runner
from scene_plan import validate


class ExactBundleTest(unittest.TestCase):
    def test_exact_recording_contract(self):
        receipt=runner.check()
        self.assertGreaterEqual(receipt['frames'],600)
        self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_missing_original_survey_fails_before_native_import(self):
        config=json.loads((ROOT/'config.json').read_text())
        self.assertIn(config['case_suffix'],('reference','contrast'))
        self.assertEqual(config['required_atoms'],[])
        self.assertEqual(config['source_packets'],[])


if __name__=='__main__':
    unittest.main()
