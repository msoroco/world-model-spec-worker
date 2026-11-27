"""Positive and adverse original activity source checks."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alley_activity import measure_original_activity,CASE_PREFIX

class AlleyActivityTests(unittest.TestCase):
    case=CASE_PREFIX+'passenger_active_stop'
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='.runtime-work')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        rows=[]
        for frame in range(900):
            rows.append({'source_kind':'original_native','case_id':self.case,'frame':frame,'time_s':frame/20,'ego_speed_mps':0.0 if 200<=frame<500 else 3.0,'ego_xy_m':[float(frame)/20,2.0],'in_business_alley':True,'ordinance_reviewed_applicable':False,'passenger_contact':220<=frame<260,'goods_contact':False,'driver_in_vehicle':True,'door_open':210<=frame<270})
        self.rows=rows;self.write()
    def write(self):
        self.history=self.root/'frames.jsonl';self.seal=self.root/'seal.json'
        raw=('\n'.join(json.dumps(r,sort_keys=True) for r in self.rows)+'\n').encode();self.history.write_bytes(raw)
        self.seal.write_text(json.dumps({'format':'original-alley-activity-seal','case_id':self.case,'history_sha256':hashlib.sha256(raw).hexdigest(),'frame_count':900,'rate_hz':20})+'\n')
    def test_original_passenger_halt_measures_without_legal_label(self):
        result=measure_original_activity(self.history,self.seal,self.case)
        self.assertEqual(result['intervals_s']['halt'],[[10.0,25.0]])
        self.assertEqual(result['intervals_s']['passenger_contact'],[[11.0,13.0]])
        self.assertEqual(result['legal_conclusion'],'unreviewed')
    def test_rejects_hash_changed(self):
        self.rows[250]['passenger_contact']=False;self.history.write_text('\n'.join(json.dumps(r) for r in self.rows)+'\n')
        with self.assertRaisesRegex(ValueError,'hash changed'):measure_original_activity(self.history,self.seal,self.case)
    def test_rejects_missing_original_frame(self):
        del self.rows[250];self.write()
        with self.assertRaisesRegex(ValueError,'incomplete original activity history'):measure_original_activity(self.history,self.seal,self.case)
    def test_rejects_non_original_frame(self):
        self.rows[250]['source_kind']='diagnostic';self.write()
        with self.assertRaisesRegex(ValueError,'frame identity'):measure_original_activity(self.history,self.seal,self.case)
    def test_rejects_unreviewed_simultaneous_activity(self):
        self.rows[250]['goods_contact']=True;self.write()
        with self.assertRaisesRegex(ValueError,'simultaneous'):measure_original_activity(self.history,self.seal,self.case)
    def test_rejects_wrong_case(self):
        with self.assertRaisesRegex(ValueError,'identity mismatch'):measure_original_activity(self.history,self.seal,CASE_PREFIX+'goods_active_load')
if __name__=='__main__':unittest.main()
