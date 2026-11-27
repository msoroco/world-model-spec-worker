"""Exact bundle identity."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check

class BundleTest(unittest.TestCase):
    def test_case(self):
        self.assertTrue(check()["selected_case_id"].endswith("__curb_parallel_clear"))
