import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check

class SelectedCountdownOffline(unittest.TestCase):
    def test_source_gate_and_identity(self):
        root = Path(__file__).resolve().parents[1]
        result = check(root)
        self.assertEqual(result["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", result["source_gate"])

if __name__ == "__main__":
    unittest.main()
