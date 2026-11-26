"""Materialized case identity and source-gated runner smoke test."""

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BundleTest(unittest.TestCase):
    def test_exact_case_static_runner(self):
        config = json.loads((ROOT / "config.json").read_text())
        self.assertTrue(config["selected_case_id"].startswith(config["assignment_id"] + "__"))
        self.assertEqual((config["rate_hz"], config["duration_s"]), (20, 45))
        result = subprocess.run([sys.executable, str(ROOT / "runner.py"), "--check"],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("static check passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
