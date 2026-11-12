import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]
REPO=PACKAGE.parents[1]
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.physical_preparation import validate


class PhysicalProofTests(unittest.TestCase):
    def test_canonical_snapshot_saved_proofs_bind_current_manifest(self):
        index=json.loads((PACKAGE/'canonical-proof-index.json').read_text())
        digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(index['manifest_sha256'],digest(PACKAGE/'execution-manifest.json'))
        self.assertEqual(len(index['cases']),4)
        for row in index['cases']:
            self.assertEqual(row['compatibility_sha256'],digest(PACKAGE/row['compatibility_receipt']))
            self.assertEqual(row['saved_sha256'],digest(PACKAGE/row['saved_receipt']))
            receipt=json.loads((PACKAGE/row['saved_receipt']).read_text())
            self.assertEqual(receipt['case_id'],row['case_id'])
            self.assertTrue(receipt['recorded_only'])
            self.assertTrue(receipt['passed'])

    def test_four_cases_have_three_outcomes_and_ordered_closure(self):
        manifest=json.loads((PACKAGE/'execution-manifest.json').read_text())
        self.assertEqual(len(manifest['cases']),4)
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                validate(REPO,PACKAGE,entry)
                receipt=json.loads((PACKAGE/entry['physical_preparation']['receipt']).read_text())
                self.assertTrue(receipt['diagnostic_fixture_only'])
                self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_stale_construction_binding_rejected(self):
        entry=json.loads((PACKAGE/'execution-manifest.json').read_text())['cases'][0]
        altered=copy.deepcopy(entry)
        altered['construction_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Stale physical preparation proof'):
            validate(REPO,PACKAGE,altered)


if __name__=='__main__':unittest.main()
