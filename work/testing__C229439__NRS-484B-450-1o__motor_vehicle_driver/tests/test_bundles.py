"""Check exact inline source snapshots and their offline receipts."""
import hashlib
import json
from pathlib import Path
import unittest

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BundleTests(unittest.TestCase):
    def test_eight_exact_bundles_include_full_media_finalizer(self):
        manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
        self.assertEqual(len(manifest['cases']), 8)
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                path = FOLDER / entry['construction']
                self.assertEqual(sha(path), entry['construction_sha256'])
                construction = json.loads(path.read_text())
                self.assertEqual(construction['case_id'], entry['case_id'])
                files = {item['path']: item for item in construction['files']}
                self.assertIn('saved_media_audit.py', files)
                self.assertIn('finalizer.py', files)
                self.assertIn('audit_media(attempt, capture_root', files['finalizer.py']['content'])
                for item in files.values():
                    if 'source' in item:
                        self.assertEqual((ROOT / item['source']).read_text(), item['content'])
                receipt = entry['offline']
                self.assertEqual(receipt['exit_code'], 0)
                self.assertEqual(receipt['construction_sha256'], entry['construction_sha256'])
                self.assertEqual(sha(FOLDER / receipt['log']), receipt['log_sha256'])


if __name__ == '__main__':
    unittest.main()
