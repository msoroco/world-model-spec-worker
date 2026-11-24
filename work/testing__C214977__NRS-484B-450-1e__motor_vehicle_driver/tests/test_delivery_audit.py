import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delivery_audit as d


class DeliveryAuditTests(unittest.TestCase):
    def test_review_requires_exact_source_binding(self):
        case = d.ASSIGNMENT+'__park_on'
        source = {'native_result':'a','native_receipt':'b','actor_rows':'c','trace':'d'}
        packet = {'format':'crosswalk-independent-physical-review','case_id':case,
                  'accepted':True,'source_hashes':source,'reviewer':'local reviewer',
                  'method':'original frame inspection','reviewed_frame_interval':[0,899]}
        self.assertEqual(d._review(packet,kind='physical',case=case,binding=source),packet)
        with self.assertRaisesRegex(ValueError,'missing or stale'):
            d._review(packet,kind='physical',case=case,binding={**source,'trace':'changed'})
        with self.assertRaisesRegex(ValueError,'missing or stale'):
            d._review({**packet,'accepted':False},kind='physical',case=case,binding=source)

    def test_diagnostic_seal_never_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'capture-seal.json').write_text(json.dumps({
                'format':'worker-sealed-capture','provenance_kind':'synthetic_fixture',
                'diagnostic_fixture':True,'restoration':{'restored':True},'frames':900})+'\n')
            (root/'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n')
            with self.assertRaisesRegex(ValueError,'Native source seal'):
                d.audit(root,d.ASSIGNMENT+'__park_on',root/'physical.json',root/'pixels.json',
                        root/'decode.json',job_id='job',attempt_number=1,
                        recording_id='recording',auditor_path=Path(d.__file__))


if __name__=='__main__':unittest.main()
