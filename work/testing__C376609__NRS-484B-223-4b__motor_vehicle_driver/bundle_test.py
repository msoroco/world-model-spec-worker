"""Materialized exact selected identity and source gate smoke tests."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BundleTest(unittest.TestCase):
    def test_static_selected_bundle(self):
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual(config['duration_s'], 45)
        self.assertEqual(config['selected_case_id'], config['case']['case_id'])
        result = subprocess.run([sys.executable, str(ROOT / 'runner.py'), '--check'],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_source_required(self):
        result = subprocess.run([sys.executable, str(ROOT / 'runner.py')],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('reviewed site', result.stderr)


if __name__ == '__main__':
    unittest.main()
