import hashlib
import json
import base64
import unittest
import zlib
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]


class PhysicalProofTests(unittest.TestCase):
    def test_historical_canonical_snapshot_is_explicitly_stale(self):
        wrapper=json.loads((PACKAGE.parent/'_shared/consolidated-proof-archives-20261123.json').read_text())
        nested=next(row for row in wrapper['files'] if row['original_path'].endswith('/c125763-stale-canonical-snapshot-20261123.json'))
        source=zlib.decompress(base64.b64decode(nested['content_zlib_base64']))
        self.assertEqual(hashlib.sha256(source).hexdigest(),nested['sha256'])
        archive=json.loads(source)
        archived={Path(row['path']).name:row for row in archive['files']}
        def original(name):
            row=archived[name]
            data=zlib.decompress(base64.b64decode(row['content_zlib_base64']))
            self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
            return data
        index=json.loads(original('canonical-proof-index.json'))
        digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(index['status'],'partial_snapshot')
        self.assertNotEqual(index['manifest_sha256'],digest(PACKAGE/'execution-manifest.json'))
        self.assertEqual(len(index['cases']),4)
        self.assertFalse(index['physical_acceptance_claimed'])
        for row in index['cases']:
            self.assertEqual(row['compatibility_sha256'],hashlib.sha256(original(row['compatibility_receipt'])).hexdigest())
            self.assertFalse((PACKAGE/row['saved_receipt']).exists())

    def test_current_manifest_tracks_four_returned_physical_receipts(self):
        manifest=json.loads((PACKAGE/'execution-manifest.json').read_text())
        self.assertEqual(len(manifest['cases']),4)
        paths=set()
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                path=entry['physical_preparation']['receipt']
                self.assertNotIn(path,paths)
                paths.add(path)
                self.assertTrue((PACKAGE/path).is_file())
                self.assertEqual(hashlib.sha256((PACKAGE/path).read_bytes()).hexdigest(),
                                 entry['physical_preparation']['sha256'])

    def test_current_exact_offline_logs_bind_all_constructions(self):
        manifest=json.loads((PACKAGE/'execution-manifest.json').read_text())
        digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        for entry in manifest['cases']:
            for candidate in [entry,*entry['candidates']]:
                with self.subTest(case=entry['case_id'], candidate=candidate.get('id','primary')):
                    self.assertEqual(candidate['construction_sha256'],digest(PACKAGE/candidate['construction']))
                    proof=candidate['offline']
                    self.assertEqual(proof['exit_code'],0)
                    self.assertEqual(proof['construction_sha256'],candidate['construction_sha256'])
                    self.assertEqual(proof['log_sha256'],digest(PACKAGE/proof['log']))


if __name__=='__main__':unittest.main()
