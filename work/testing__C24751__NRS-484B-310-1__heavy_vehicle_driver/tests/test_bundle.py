"""Exact source-gated flashing-red materialization."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check

class ExactBundleTest(unittest.TestCase):
    def test_selected_identity(self):
        self.assertTrue(check().endswith("__crosswalk_stop"))
