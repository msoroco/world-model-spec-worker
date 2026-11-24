"""Exact diagnostic materialization inventory; no source authority claim."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DiagnosticBundleTest(unittest.TestCase):
    def test_five_exact_source_honest_bundles(self):
        manifest = json.loads((ROOT / 'diagnostic-manifest.json').read_text())
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        self.assertTrue(manifest['diagnostic_only'])
        self.assertEqual({entry['case_id'] for entry in manifest['cases']},
                         {case['case_id'] for case in plan['cases']})
        for entry in manifest['cases']:
            path = ROOT / entry['construction']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             entry['construction_sha256'])
            construction = json.loads(path.read_text())
            self.assertEqual(construction['case_id'], entry['case_id'])
            self.assertTrue(construction['diagnostic_only'])
            files = {item['path']: item['content'] for item in construction['files']}
            config = json.loads(files['config.json'])
            scene = json.loads(files['scene.json'])
            self.assertEqual(config['case'], scene)
            self.assertEqual(config['source_packets'], [])
            self.assertEqual(len(config['cameras']), 4)
            self.assertEqual(config['rate_hz'], 20)
            self.assertIn('tests/test_bundle.py', files)
