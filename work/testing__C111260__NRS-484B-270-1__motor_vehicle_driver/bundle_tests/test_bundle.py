"""Offline structural checks for an exact bicycle encounter bundle."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BundleTests(unittest.TestCase):
    def test_exact_selection_and_four_views(self):
        config = json.loads((ROOT / 'config.json').read_text())
        selected = config['selected_case_id']
        self.assertEqual(config['case']['case_id'], selected)
        self.assertEqual(config['frame_count'], 900)
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual([c['name'] for c in config['cameras']], [
            'overview', 'approach', 'reference_corner', 'driver_reference'])
        result = subprocess.run([sys.executable, str(ROOT / 'runner.py'), '--check'],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_sources_and_finalizer_present(self):
        for name in ('native_capture.py', 'rider_sources.py', 'saved_attempt.py',
                     'original_source_index.py', 'delivery_decode.py',
                     'analysis.py', 'delivery_audit.py', 'comparison_audit.py'):
            self.assertTrue((ROOT / name).is_file(), name)


if __name__ == '__main__':
    unittest.main()
