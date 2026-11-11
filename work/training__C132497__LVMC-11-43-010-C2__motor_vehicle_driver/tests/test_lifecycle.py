"""Synthetic, motion-free CPU checks of the pinned closure receipt sequence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.saved_processing import (record_native_exit,
    acknowledge_owner_release,_closure)
from worker_exchange.common import sha


class ClosureReceiptMechanics(unittest.TestCase):
    def fixture(self,root):
        root=Path(root)
        (root/'construction.json').write_text('{"synthetic_test_only":true}\n')
        (root/'runner.py').write_text('# synthetic test only\n')
        (root/'source.txt').write_text('synthetic test source\n')
        seal={'format':'worker-sealed-capture','synthetic_test_only':True,
              'events':['capture_finished','encoders_closed','restoration_verified'],
              'sources':{'source.txt':sha(root/'source.txt')},
              'native_revision':{'construction_sha256':sha(root/'construction.json'),
                                 'runner_sha256':sha(root/'runner.py')}}
        (root/'capture-seal.json').write_text(json.dumps(seal)+'\n')

    def test_order_and_stale_source_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.fixture(root)
            receipt=root/'owner-release.json'
            with self.assertRaisesRegex(ValueError,'process has not exited'):
                acknowledge_owner_release(root,receipt,True)
            exit_record=record_native_exit(root)
            self.assertEqual(exit_record['event'],'native_exit')
            with self.assertRaisesRegex(ValueError,'Operator must attest'):
                acknowledge_owner_release(root,receipt,False)
            owner=acknowledge_owner_release(root,receipt,True)
            self.assertTrue(owner['no_resource_operation_performed'])
            _closure(root,receipt,'synthetic_fixture',True)
            (root/'source.txt').write_text('changed synthetic source\n')
            with self.assertRaisesRegex(ValueError,'Sealed original changed'):
                _closure(root,receipt,'synthetic_fixture',True)

    def test_seal_event_order_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.fixture(root)
            path=root/'capture-seal.json';seal=json.loads(path.read_text())
            seal['events'][0],seal['events'][1]=seal['events'][1],seal['events'][0]
            path.write_text(json.dumps(seal)+'\n')
            with self.assertRaisesRegex(ValueError,'closure ordering'):
                record_native_exit(root)


if __name__=='__main__':unittest.main()
