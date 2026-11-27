import json
import unittest
from pathlib import Path


class BundleTest(unittest.TestCase):
    def test_exact_case_shape(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'config.json').read_text())
        scene = json.loads((root / 'scene.json').read_text())
        self.assertEqual(config['selected_case_id'], scene['case_id'])
        self.assertEqual(config['case']['conduct'], scene['conduct'])
        self.assertEqual(config['case']['duration_relation'], scene['duration_relation'])
        self.assertEqual(config['duration_s'] * config['rate_hz'], 900)
        self.assertEqual([c['name'] for c in config['cameras']], ['overview', 'approach', 'reference_corner', 'driver_reference'])
