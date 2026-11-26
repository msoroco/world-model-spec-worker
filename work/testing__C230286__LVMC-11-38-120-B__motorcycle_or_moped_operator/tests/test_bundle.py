"""Runs after the selected case construction is materialized by runtime.py."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner


class BundleTests(unittest.TestCase):
    def test_exact_selected_case_and_profile(self):
        selected = runner.check()
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(selected["case_id"], config["selected_case_id"])
        self.assertEqual(config["duration_s"] * config["rate_hz"], 600)

    def test_original_sources_required_before_native_connection(self):
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000",
                                "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "reviewed source packet"):
                    runner.main()


if __name__ == "__main__":
    unittest.main()
