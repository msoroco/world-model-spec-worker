import json
import unittest
from pathlib import Path
from runner import check

class ExactYieldOffline(unittest.TestCase):
    def test_source_gated_static_bundle(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", selected["source_gate"])

if __name__ == "__main__":
    unittest.main()
