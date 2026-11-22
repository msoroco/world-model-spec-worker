import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from delivery_audit import audit as audit_delivery
from response_history_audit import audit,bracket
from test_delivery_audit import DeliveryAuditTests


class OriginalResponseBracketTests(unittest.TestCase):
    def pair(self,root):
        records=[]
        for suffix in ('clear_path','crossing'):
            folder=root/suffix;folder.mkdir()
            attempt,processing,decode,case=DeliveryAuditTests().fixture(
                folder,ROOT.name+'__wheelchair_'+suffix)
            receipt=audit_delivery(attempt,processing,decode,case,
                                   media_verify=lambda *args,**kwargs:True)
            records.append((attempt,receipt))
        return records

    def test_sealed_original_pair_brackets_authored_response(self):
        with tempfile.TemporaryDirectory() as temp:
            (clear,clear_receipt),(crossing,crossing_receipt)=self.pair(Path(temp))
            result=audit(clear,crossing,clear_receipt,crossing_receipt)
            self.assertTrue(result['passed'])
            self.assertEqual(result['above_engineering_boundary_frames'],[100])
            self.assertEqual(result['below_engineering_boundary_frames'],[101])
            self.assertEqual(result['observed_crossing_time_to_path_range_s'],[2.0,3.5])
            self.assertIsNone(result['legal_due_care_verdict'])
            rows=[json.loads(line) for line in (crossing/'encounter-history.jsonl').read_text().splitlines()]
            rows[0]['control_inputs']['ego_speed_mps']=4
            (crossing/'encounter-history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'response original source or receipt stale'):
                audit(clear,crossing,clear_receipt,crossing_receipt)

    def test_missing_bracket_is_rejected_without_legal_inference(self):
        clear=[{'frame':1,'approaching_lane':False,'time_to_path_s':2.0,'brake':0}]
        crossing=[{'frame':2,'approaching_lane':True,'time_to_path_s':2.0,'brake':1}]
        with self.assertRaisesRegex(ValueError,'lacks above/below'):
            bracket(crossing,clear,3.0)


if __name__=='__main__':unittest.main()
