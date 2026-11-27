"""Materialized exact runner smoke test, independent of CARLA."""

import json
import subprocess
import sys
import unittest
from pathlib import Path


class BundleTest(unittest.TestCase):
    def test_exact_runner_static(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'config.json').read_text())
        result = subprocess.run([sys.executable, str(root / 'runner.py'), '--check'],
                                cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(config['selected_case_id'], result.stdout)


if __name__ == '__main__':
    unittest.main()
