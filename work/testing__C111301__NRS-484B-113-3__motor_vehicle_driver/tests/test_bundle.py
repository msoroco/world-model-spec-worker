"""Materialized bundle keeps one exact case and four canonical cameras."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import check


class BundleTests(unittest.TestCase):
    def test_exact_selected_case(self):
        result = check(ROOT)
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertIn(config['selected_case_id'], result['selected_cases'])
        self.assertTrue(result['source_site_required_at_capture'])
        self.assertFalse(result['physical_acceptance_claimed'])


if __name__ == '__main__':
    unittest.main()
