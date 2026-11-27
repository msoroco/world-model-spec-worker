"""Exercise every exact package request through the published runner."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((PACKAGE / "execution-manifest.json").read_text())


class ExactRunnerTests(unittest.TestCase):
    def test_six_exact_requests(self):
        for entry in MANIFEST["cases"]:
            condition = entry["case_id"].removeprefix(PACKAGE.name + "__")
            with self.subTest(condition=condition):
                output = subprocess.check_output(
                    [sys.executable, str(PACKAGE / "runner.py"), "--case", condition,
                     "--check"], text=True)
                checked = json.loads(output)
                self.assertEqual(checked["case_id"], entry["case_id"])
                self.assertEqual(checked["camera_count"], 4)
                self.assertFalse(checked["physical_acceptance_claimed"])

    def test_rejects_unknown_condition(self):
        result = subprocess.run(
            [sys.executable, str(PACKAGE / "runner.py"), "--case", "invented",
             "--check"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
