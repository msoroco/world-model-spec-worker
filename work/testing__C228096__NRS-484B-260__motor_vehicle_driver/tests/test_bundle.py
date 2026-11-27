"""Exact private-way inline import and identity contract."""
import json
from pathlib import Path
import unittest
import runner

class BundleTest(unittest.TestCase):
    def test_exact_identity(self):
        root = Path(__file__).resolve().parents[1]
        config = runner.check(root)
        self.assertEqual(config["selected_case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertEqual(config["frame_count"], 900)

if __name__ == "__main__":
    unittest.main()
