"""Root alias identity sanity test."""
import json
from pathlib import Path
import unittest

class AliasTest(unittest.TestCase):
    def test_all_exact_cases_listed(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text())
        self.assertEqual(len(config["supported_case_ids"]), 3)
        self.assertEqual(config["selected_case_id"], config["supported_case_ids"][0])
