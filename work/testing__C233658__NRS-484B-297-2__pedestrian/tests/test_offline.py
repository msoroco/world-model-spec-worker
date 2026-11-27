import json
import unittest
from pathlib import Path
from runner import check

class ExactWalkingOffline(unittest.TestCase):
    def test_case_and_source_gate(self):
        result = check(Path(__file__).resolve().parents[1])
        self.assertEqual(result["case_id"], json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", result["source_gate"])

if __name__ == "__main__":
    unittest.main()
