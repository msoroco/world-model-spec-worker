import json
import unittest
from pathlib import Path
import runner

class BundleTest(unittest.TestCase):
    def test_exact_primary(self):
        checked = runner.check()
        config = json.loads((Path(__file__).parents[1]/'config.json').read_text())
        self.assertEqual(checked['case_id'], config['case_id'])
        self.assertEqual(checked['frames'], 600)
        self.assertEqual(len(checked['source_cameras']), 4)
        self.assertFalse(checked['physical_acceptance_claimed'])
