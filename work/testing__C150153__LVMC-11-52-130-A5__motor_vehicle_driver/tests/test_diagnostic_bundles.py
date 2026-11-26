"""Source and identity checks for the 12 exact diagnostic constructions."""
import hashlib
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


class DiagnosticBundleTests(unittest.TestCase):
    def test_exact_manifest_and_source_hashes(self):
        plan = json.loads((HERE / 'case-plan.json').read_text())
        manifest = json.loads((HERE / 'execution-manifest.diagnostic.json').read_text())
        self.assertEqual({row['case_id'] for row in manifest['cases']},
                         {row['case_id'] for row in plan['cases']})
        self.assertEqual(len(manifest['cases']), 12)
        for row in manifest['cases']:
            self.assertEqual(row['candidate_risk']['status'], 'physical')
            for candidate in (row, row['candidates'][0]):
                path = HERE / candidate['construction']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                 candidate['construction_sha256'])
                bundle = json.loads(path.read_text())
                self.assertTrue(bundle['diagnostic_only'])
                self.assertEqual(bundle['case_id'], row['case_id'])
                files = {item['path']: item['content'] for item in bundle['files']}
                scene = json.loads(files['scene.json'])
                self.assertEqual(scene['source_kind'], 'synthetic_diagnostic')
                self.assertEqual(scene['case_plan_sha256'],
                                 hashlib.sha256((HERE / 'case-plan.json').read_bytes()).hexdigest())

    def test_offline_receipts_bind_both_candidates(self):
        index = json.loads((HERE / 'diagnostic-offline-index.json').read_text())
        self.assertEqual(index['source_kind'], 'synthetic_diagnostic')
        self.assertFalse(index['physical_acceptance'])
        self.assertEqual(len(index['receipts']), 24)
        self.assertEqual({r['candidate_id'] for r in index['receipts']},
                         {'primary', 'fallback1'})
        self.assertTrue(all(r['exit_code'] == 0 for r in index['receipts']))


if __name__ == '__main__':
    unittest.main()
