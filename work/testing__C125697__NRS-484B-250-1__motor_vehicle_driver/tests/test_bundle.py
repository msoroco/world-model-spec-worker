import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_and_source_contract(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text())
        self.assertEqual(runner.check(), config["selected_case_id"])

    def test_refuses_unsourced_native_launch(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original roadway crossing"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
