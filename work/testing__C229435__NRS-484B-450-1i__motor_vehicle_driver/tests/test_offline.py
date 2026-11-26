import json
import unittest
from pathlib import Path
from runner import check

class SelectedRailParkingOffline(unittest.TestCase):
    def test_reviewed_source_gate(self):
        root = Path(__file__).resolve().parents[1]
        result = check(root)
        self.assertEqual(result["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", result["source_gate"])

if __name__ == "__main__":
    unittest.main()
