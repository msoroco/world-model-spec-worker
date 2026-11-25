import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_preflight(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsourced_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaises(SystemExit):
                runner.main()


if __name__ == "__main__":
    unittest.main()
