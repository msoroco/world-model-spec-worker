import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class BundleTests(unittest.TestCase):
    def test_exact_selected_case(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(root), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_unsourced_native_entry_rejected(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "reviewed original C111278 site packet missing"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
