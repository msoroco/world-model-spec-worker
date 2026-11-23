import hashlib
import json
import unittest
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]


class PhysicalProofTests(unittest.TestCase):
    def test_historical_canonical_snapshot_is_explicitly_stale(self):
        index=json.loads((PACKAGE/'canonical-proof-index.json').read_text())
        digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(index['status'],'partial_snapshot')
        self.assertNotEqual(index['manifest_sha256'],digest(PACKAGE/'execution-manifest.json'))
        self.assertEqual(len(index['cases']),4)
        self.assertFalse(index['physical_acceptance_claimed'])
        for row in index['cases']:
            self.assertEqual(row['compatibility_sha256'],digest(PACKAGE/row['compatibility_receipt']))
            self.assertFalse((PACKAGE/row['saved_receipt']).exists())

    def test_current_manifest_declares_four_distinct_physical_receipt_gaps(self):
        manifest=json.loads((PACKAGE/'execution-manifest.json').read_text())
        self.assertEqual(len(manifest['cases']),4)
        paths=set()
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                path=entry['physical_preparation']['receipt']
                self.assertNotIn(path,paths)
                paths.add(path)
                self.assertFalse((PACKAGE/path).exists())

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
