"""The exact runner must reject absent source review before CARLA use."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "runner.py"


class RunnerPreflightTest(unittest.TestCase):
    def test_offline_check_and_missing_original_site(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env.pop("C158196_ORIGINAL_SITE_BUNDLE", None)
        passed = subprocess.run([sys.executable, str(RUNNER), "--check"],
                                env=env, capture_output=True, text=True)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertIn('"physical_acceptance_claimed": false', passed.stdout)
        failed = subprocess.run([sys.executable, str(RUNNER), "--output-dir",
                                 str(RUNNER.parent)], env=env, capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("source-reviewed original C158196 site bundle required", failed.stderr)
        self.assertNotIn("No module named 'carla'", failed.stderr)


if __name__ == "__main__":
    unittest.main()
