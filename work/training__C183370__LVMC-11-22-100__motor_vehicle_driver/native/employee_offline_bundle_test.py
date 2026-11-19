"""Materialized employee-route bundle CPU checks."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'native'))
import runner


class EmployeeBundleTest(unittest.TestCase):
    def test_exact_source_contract(self):
        receipt = runner.check()
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertGreaterEqual(receipt['frames'], 600)
        self.assertEqual(config['control_kind'], 'employee_exception')
        self.assertIn(config['case_suffix'], ('employee_crossing', 'nonemployee_crossing'))
        self.assertEqual(len(config['cameras']), 4)
        self.assertFalse(receipt['physical_acceptance_claimed'])


if __name__ == '__main__':
    unittest.main()
