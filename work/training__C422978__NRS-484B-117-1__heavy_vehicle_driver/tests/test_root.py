"""Source-bound root Native request checks."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeRequestTest(unittest.TestCase):
    def test_reference_native_request(self):
        process = subprocess.run([sys.executable, str(ROOT / 'runner.py'), '--check'],
                                 capture_output=True, text=True, check=True)
        result = json.loads(process.stdout)
        self.assertEqual(result['requested_frames'], 600)
        self.assertFalse(result['original_native_observed'])

    def test_current_four_view_profile(self):
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual([camera['name'] for camera in config['cameras']],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertEqual(config['duration_s'], 30)
