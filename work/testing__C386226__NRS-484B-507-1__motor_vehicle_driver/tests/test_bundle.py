"""Exact source-gated Native bundle check."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check

class BundleTest(unittest.TestCase):
    def test_exact_bundle(self):
        case_id, case = check()
        self.assertEqual(case_id, 'testing__C386226__NRS-484B-507-1__motor_vehicle_driver__stop_no_material')
        self.assertEqual(case.name, 'stop_no_material')
