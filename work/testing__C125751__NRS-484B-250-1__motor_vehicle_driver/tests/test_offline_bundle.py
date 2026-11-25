"""Source-gated exact bundle checks for the portable offline materialization."""
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OfflineBundleTest(unittest.TestCase):
    def test_selected_case_is_static_and_native_sources_are_required(self):
        spec = json.loads((ROOT / 'case-spec.json').read_text())
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual(spec['case_id'], config['selected_case_id'])
        self.assertEqual(config['duration_frames'], 1100)
        self.assertEqual(len(config['cameras']), 4)
        self.assertTrue(all(spec[key] is None for key in (
            'source_packet_sha256', 'map_sha256', 'crossing_id',
            'ego_route_sha256', 'other_route_sha256',
            'ego_blueprint', 'other_blueprint')))
        command = [sys.executable, str(ROOT / 'runner.py'),
                   '--output-dir', str(ROOT / 'uncreated-native-attempt')]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source or capture binding absent', result.stderr)
        self.assertFalse((ROOT / 'uncreated-native-attempt').exists())


if __name__ == '__main__':
    unittest.main()
