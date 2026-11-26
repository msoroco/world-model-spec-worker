"""Exact source-gated hydrant materialization."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check

class ExactBundleTest(unittest.TestCase):
    def test_selected_identity(self):
        self.assertTrue(check().endswith("__upstream_inside"))
