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
from worker_exchange.native_output import seal_capture


class ClosureReceiptMechanics(unittest.TestCase):
    def test_real_seal_call_and_release_on_motion_free_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'construction.json').write_text('{"synthetic_test_only":true}\n')
            (root/'runner.py').write_text('# synthetic test only\n')
            (root/'trace.jsonl').write_text('')
            (root/'video_frames.jsonl').write_text('')
            (root/'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n')
            with self.assertRaisesRegex(ValueError,'verified restoration'):
                seal_capture(root,frames=0,restoration={'restored':False},
                             errors=[],encoder_exit_codes={'overview':0})
            with self.assertRaisesRegex(ValueError,'failed encoders'):
                seal_capture(root,frames=0,restoration={'restored':True},
                             errors=[],encoder_exit_codes={'overview':1})
            self.assertFalse((root/'capture-seal.json').exists())
            seal=seal_capture(root,frames=0,restoration={'restored':True},
                              errors=[],encoder_exit_codes={'overview':0},
                              context={'synthetic_test_only':True})
            self.assertTrue(seal['diagnostic_fixture'])
            self.assertFalse(seal['physical_acceptance_claimed'])
            self.assertEqual(seal['events'],
                ['capture_finished','encoders_closed','restoration_verified'])
            exit_record=record_native_exit(root)
            receipt=root/'owner-release.json'
            owner=acknowledge_owner_release(root,receipt,True)
            _closure(root,receipt,'synthetic_fixture',True)
            self.assertEqual([*seal['events'],exit_record['event'],owner['event'],
                              'saved_processing_started'],
                ['capture_finished','encoders_closed','restoration_verified',
                 'native_exit','owner_released','saved_processing_started'])

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
