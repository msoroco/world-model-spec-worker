"""Exact bundle remains source-gated while its CPU check is executable."""
import json
import unittest
from pathlib import Path

from runner import check


class BundleTest(unittest.TestCase):
    def test_exact_case_and_source_gate(self):
        config = json.loads(Path('config.json').read_text())
        result = check(config)
        self.assertEqual(result['case_id'], config['selected_case_id'])
        self.assertFalse(result['physical_acceptance'])
        self.assertIsNone(result['legal_verdict'])
