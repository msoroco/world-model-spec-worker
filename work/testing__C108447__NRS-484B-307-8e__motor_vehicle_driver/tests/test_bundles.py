import hashlib
import json
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BundleTests(unittest.TestCase):
    def test_six_exact_source_sealed_inline_constructions(self):
        manifest_path = FOLDER / 'execution-manifest.draft.json'
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest['format'], 'worker-execution-manifest')
        self.assertEqual(len(manifest['cases']), 6)
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                construction_path = FOLDER / entry['construction']
                self.assertEqual(sha(construction_path), entry['construction_sha256'])
                construction = json.loads(construction_path.read_text())
                self.assertEqual(construction['case_id'], entry['case_id'])
                self.assertEqual(construction['entrypoint'], 'runner.py')
                files = {item['path']: item for item in construction['files']}
                self.assertIn('tests/test_bundle.py', files)
                config = json.loads(files['config.json']['content'])
                self.assertEqual(config['selected_case_id'], entry['case_id'])
                recipe = FOLDER.parents[1] / entry['fixture_recipe']
                self.assertTrue(recipe.is_file())
                for source in json.loads(recipe.read_text())['sources']:
                    self.assertEqual(sha(FOLDER.parents[1] / source['source']), source['sha256'])
                for item in construction['files']:
                    if 'source' in item:
                        self.assertEqual((FOLDER.parents[1] / item['source']).read_text(), item['content'])

    def test_six_offline_receipts_bind_immutable_draft_and_logs(self):
        receipt = json.loads((FOLDER / 'draft-offline-receipts.json').read_text())
        manifest = FOLDER / 'execution-manifest.draft.json'
        self.assertEqual(receipt['manifest_sha256'], sha(manifest))
        self.assertEqual(len(receipt['cases']), 6)
        for entry in receipt['cases']:
            self.assertEqual(entry['exit_code'], 0)
            self.assertEqual(sha(FOLDER / entry['log']), entry['log_sha256'])
            self.assertFalse(entry['physical_acceptance_claimed'])

    def test_six_diagnostic_materializations_and_case_observation_proof(self):
        receipt = json.loads((FOLDER / 'diagnostic-receipts.json').read_text())
        self.assertEqual(len(receipt['cases']), 6)
        self.assertEqual(sha(FOLDER / receipt['observation_proof']), receipt['observation_proof_sha256'])
        proof = json.loads((FOLDER / receipt['observation_proof']).read_text())
        self.assertTrue(proof['diagnostic_only'])
        self.assertEqual(proof['case_count'], 6)
        for row in receipt['cases']:
            self.assertEqual(sha(FOLDER / row['recipe']), row['recipe_sha256'])
            self.assertEqual(sha(FOLDER / row['specification']), row['specification_sha256'])
            self.assertEqual(sha(FOLDER / row['materialization_log']), row['materialization_log_sha256'])
            self.assertFalse(row['physical_acceptance_claimed'])


if __name__ == '__main__':
    unittest.main()
