import json
import unittest
from pathlib import Path
from runner import check

class SelectedCaseTest(unittest.TestCase):
    def test_exact_source_gate(self):
        root = Path(__file__).resolve().parents[1]
        config = check(root)
        self.assertFalse(config["case"]["diagnostic_only"])
