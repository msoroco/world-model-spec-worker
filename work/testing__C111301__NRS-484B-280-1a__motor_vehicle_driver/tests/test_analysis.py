import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('wheelchair_analysis',ROOT/'analysis.py')
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def body(x,y):return [[x,y,0],[x+1,y,0],[x+1,y+1,0],[x,y+1,0]]


class WheelchairAnalysisTests(unittest.TestCase):
    def fixture(self,root):
        context=root/'intersection-context.json'
        context.write_text(json.dumps({'route_source':'original/map','manual_wheelchair_asset_source':'original/asset'}))
        rows=[]
        for index,x in enumerate((-5,-3)):
            rows.append({'frame':100+index,'time_s':index/20,
                         'ego_body_vertices_m':body(x,0),'ego_speed_mps':2,
                         'ego_brake':0 if index==0 else 1,
                         'person':{'role':'person_in_manual_wheelchair','source_ref':'original/person',
                                   'body_vertices_m':body(0,0)},
                         'manual_wheelchair':{'kind':'manual_wheelchair','source_ref':'original/chair',
                                              'body_vertices_m':body(0,0)},
                         'surface_gap_m':4 if index==0 else 2,'contact_event':False})
        history=root/'encounter-history.jsonl'
        history.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        (root/'acquisition.json').write_text(json.dumps({name:{'kind':'original_native','sha256':sha(root/name)}
            for name in ('encounter-history.jsonl','intersection-context.json')}))
        return history

    def test_measures_original_braking_gap_without_legal_cutoff(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            value=analysis.measure(root)
            self.assertEqual(value['minimum_surface_gap_m'],2)
            self.assertEqual(value['first_brake_frame'],101)
            self.assertEqual(value['contact_frames'],[])
            self.assertEqual(value['legal_due_care_verdict'],'unresolved')
    def test_rejects_stale_source_and_reported_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);history=self.fixture(root)
            with history.open('a') as stream:stream.write('{}\n')
            with self.assertRaisesRegex(ValueError,'stale original'):
                analysis.measure(root)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);history=self.fixture(root)
            rows=[json.loads(line) for line in history.read_text().splitlines()]
            rows[1]['surface_gap_m']=10
            history.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            sources=json.loads((root/'acquisition.json').read_text())
            sources['encounter-history.jsonl']['sha256']=sha(history)
            (root/'acquisition.json').write_text(json.dumps(sources))
            with self.assertRaisesRegex(ValueError,'reported surface gap'):
                analysis.measure(root)


if __name__=='__main__':unittest.main()
