import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_and_action(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_diagnostic_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Native host, port"):
                runner.main()

    def test_native_requires_original_source_before_client_import(self):
        with patch("sys.argv", ["runner.py", "--output-dir", ".",
                                "--host", "localhost", "--port", "2000"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "original survey and source-hashed operator"):
                    runner.main()


if __name__ == "__main__":
    unittest.main()
