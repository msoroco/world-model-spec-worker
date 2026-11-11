import json
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RootContractTests(unittest.TestCase):
    def test_common_dispatch_inventory_and_camera_plan(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        config = json.loads((ROOT / 'config.json').read_text())
        construction = json.loads((ROOT / 'construction.json').read_text())
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        self.assertEqual(config['supported_case_ids'], [item['case_id'] for item in manifest['cases']])
        self.assertEqual(plan['camera_plan']['duration_s'], config['duration_s'])
        self.assertEqual([item['name'] for item in config['cameras']],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        for item in construction['files']:
            self.assertEqual(item['content'], (ROOT / item['path']).read_text())

    def test_aggregate_saved_proofs_bind_current_manifest(self):
        manifest_path = ROOT / 'execution-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        index = json.loads((ROOT / 'aggregate-saved/index.json').read_text())
        sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(index['manifest_sha256'], sha(manifest_path))
        self.assertEqual({item['case_id'] for item in index['cases']},
                         {item['case_id'] for item in manifest['cases']})
        for entry in manifest['cases']:
            proof = next(item for item in index['cases'] if item['case_id'] == entry['case_id'])
            receipt_path = ROOT / proof['receipt']
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(proof['sha256'], sha(receipt_path))
            self.assertEqual(receipt['manifest_sha256'], index['manifest_sha256'])
            self.assertTrue(receipt['originals_preserved'])
            self.assertTrue(entry['post_capture']['recorded_only'])
            self.assertEqual(entry['post_capture']['test_log_sha256'],
                             sha(ROOT / entry['post_capture']['test_log']))


if __name__ == '__main__':
    unittest.main()
