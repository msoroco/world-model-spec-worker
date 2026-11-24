import hashlib
import json
import base64
import unittest
import zlib
import tarfile
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]


class PhysicalProofTests(unittest.TestCase):
    def test_historical_canonical_snapshot_is_explicitly_stale(self):
        archive_path=PACKAGE.parent/'_shared/cpu-proof-history-plus-20261123.tar.xz'
        with tarfile.open(archive_path,'r:xz') as packed:
            source=packed.extractfile('consolidated-proof-archives-20261123.json')
            self.assertIsNotNone(source)
            wrapper=json.load(source)
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
        replay=json.loads((PACKAGE/'case-plan.json').read_text())['current_manifest_saved_replay_20261123']
        self.assertEqual(replay['manifest_sha256'],
                         hashlib.sha256((PACKAGE/'execution-manifest.json').read_bytes()).hexdigest())
        self.assertEqual({row['case_id'] for row in replay['rows']},
                         {entry['case_id'] for entry in manifest['cases']})
        bound=PACKAGE/replay['first_primary_bound_log']
        self.assertEqual(hashlib.sha256(bound.read_bytes()).hexdigest(),
                         replay['first_primary_bound_log_sha256'])
        self.assertEqual(manifest['cases'][0]['post_capture']['test_log_sha256'],
                         replay['first_primary_bound_log_sha256'])
        self.assertEqual(json.loads(bound.read_text())['result_sha256'],
                         json.loads(zlib.decompress(base64.b64decode(
                             replay['rows'][0]['saved_processing']['log_zlib_base64'])))['result_sha256'])
        paths=set()
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                path=entry['physical_preparation']['receipt']
                self.assertNotIn(path,paths)
                paths.add(path)
                self.assertTrue((PACKAGE/path).is_file())
                self.assertEqual(hashlib.sha256((PACKAGE/path).read_bytes()).hexdigest(),
                                 entry['physical_preparation']['sha256'])
        for row in replay['rows']:
            self.assertEqual(row['candidate_selection']['manifest_sha256'],replay['manifest_sha256'])
            self.assertEqual(row['candidate_selection']['case_id'],row['case_id'])
            self.assertEqual(row['candidate_selection']['candidate_id'],'primary')
            entry=next(item for item in manifest['cases'] if item['case_id']==row['case_id'])
            standalone=PACKAGE/entry['post_capture']['test_log']
            self.assertTrue(standalone.is_file())
            self.assertEqual(hashlib.sha256(standalone.read_bytes()).hexdigest(),
                             entry['post_capture']['test_log_sha256'])
            self.assertIn('No Native or legal acceptance',entry['post_capture']['proof_scope'])
            self.assertEqual(json.loads(standalone.read_text())['result_sha256'],
                             row['saved_processing']['result_sha256'])
            for stage in ('compatibility','saved_processing'):
                proof=row[stage]
                source=zlib.decompress(base64.b64decode(proof['log_zlib_base64'],validate=True))
                self.assertEqual(hashlib.sha256(source).hexdigest(),proof['log_sha256'])
                self.assertEqual(len(source),proof['log_bytes'])
                output=json.loads(source)
                self.assertEqual(output['case_id'],row['case_id'])
                self.assertTrue(output['passed'])
                if stage=='saved_processing':
                    self.assertTrue(output['recorded_only'])
                    self.assertTrue(output['originals_preserved'])
                    self.assertEqual(output['timestamp_joins']['frames'],60)
                    self.assertTrue(output['timestamp_joins']['passed'])
                    self.assertFalse(output['physical_acceptance_claimed'])
                    self.assertFalse(output['legal_acceptance_claimed'])

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
