"""Materialized exact-case software checks; does not simulate or claim motion."""
import json
import unittest
from pathlib import Path
import runner
from following_measurements import analyze

class BundleTests(unittest.TestCase):
    def test_pinned_case_and_camera_contract(self):
        config=json.loads(Path('config.json').read_text())
        self.assertEqual(runner.validate_config(config)['selected_case_id'],runner.CASE)
        self.assertEqual(config['rate_hz']*config['duration_s'],900)
    def test_analysis_requires_original_history(self):
        with self.assertRaisesRegex(ValueError,'Missing original source'):
            analyze(Path('.'))
if __name__=='__main__':unittest.main()
