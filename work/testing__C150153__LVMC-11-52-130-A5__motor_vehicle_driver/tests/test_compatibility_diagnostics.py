"""Check that every synthetic compatibility source stays exact and source hashed."""
import hashlib
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


class CompatibilityDiagnosticTests(unittest.TestCase):
    def test_twelve_case_specific_900_frame_recipes(self):
        manifest = json.loads((HERE / 'execution-manifest.source-bound-diagnostic.json').read_text())
        self.assertEqual(manifest['status'],
                         'synthetic_diagnostic_only_unselected_original_capture_pending')
        self.assertEqual(len(manifest['cases']), 12)
        for entry in manifest['cases']:
            case_id = entry['case_id']
            kind = case_id.removeprefix(HERE.name + '__')
            with self.subTest(case=kind):
                self.assertTrue(entry['diagnostic_only'])
                construction = HERE / entry['construction']
                self.assertEqual(hashlib.sha256(construction.read_bytes()).hexdigest(),
                                 entry['construction_sha256'])
                recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
                spec_path = ROOT / recipe['generator']['source']
                self.assertLessEqual(spec_path.stat().st_size, 2 * 1024 * 1024)
                self.assertEqual(hashlib.sha256(spec_path.read_bytes()).hexdigest(),
                                 recipe['generator']['sha256'])
                spec = json.loads(spec_path.read_text())
                self.assertEqual(len(spec['graphs']), 900)
                self.assertEqual(len(spec['files']['capture/evidence.jsonl'].splitlines()), 900)
                self.assertEqual(len(spec['files']['capture/native/frames.jsonl'].splitlines()), 900)
                self.assertEqual({v['frames'] for v in spec['videos']}, {900})
                self.assertEqual(json.loads(spec['files']['capture/manifest.json'])['case_id'], case_id)
                for source in recipe['sources']:
                    path = ROOT / source['source']
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source['sha256'])
                seal_source = next(v for v in recipe['sources'] if v['path'] == 'capture-seal.json')
                seal = json.loads((ROOT / seal_source['source']).read_text())
                self.assertEqual(seal['provenance_kind'], 'synthetic_fixture')
                self.assertEqual(seal['case_id'], case_id)


if __name__ == '__main__':
    unittest.main()
