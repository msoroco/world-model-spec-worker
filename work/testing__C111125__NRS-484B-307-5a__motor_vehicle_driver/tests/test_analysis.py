import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('arrow_analysis',ROOT/'analysis.py')
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)
sys.path.remove(str(ROOT))


def write_fixture(root,*,occupied=True):
    root=Path(root);head=7
    context={'facing_head_id':head,'stop_line_x_m':-8,
             'intersection_bounds_m':[-5,-5,8,5],
             'adjacent_crosswalk_bounds_m':[[-8,-5,-5,5],[8,-5,11,5]]}
    (root/'intersection-context.json').write_text(json.dumps(context)+'\n')
    signals=[];ego=[];traffic=[]
    for frame,x in enumerate((-12,-10,-9,-8,-7,-4,0,12)):
        time_s=frame/20
        aspect={'source_verified':True,'source_ref':'original signal head',
                'head_id':head,'observed_frame':frame,
                'illuminated_indications':[{'color':'green','shape':'arrow','direction':'straight'}]}
        signals.append({'frame':frame,'time_s':time_s,'facing_head_id':head,'aspect':aspect})
        ego.append({'frame':frame,'time_s':time_s,
                    'body_vertices_m':[[x,-.5,0],[x+1,-.5,0],[x+1,.5,0],[x,.5,0]],
                    'heading_deg':0})
        persons=[]
        if occupied and frame in (1,2):
            persons=[{'id':'pedestrian-1','role':'pedestrian','lawfully_present':True,
                      'lawful_presence_source':'original crosswalk phase',
                      'body_vertices_m':[[-7,-.5,0],[-6,-.5,0],[-6,.5,0],[-7,.5,0]]}]
        traffic.append({'frame':frame,'time_s':time_s,'participants':persons})
    for name,records in [('signal-head-history.jsonl',signals),('ego-body-history.jsonl',ego),('participant-history.jsonl',traffic)]:
        (root/name).write_text(''.join(json.dumps(row)+'\n' for row in records))
    acquisition={name:{'kind':'original_native','sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()}
                 for name in analysis.SOURCES}
    (root/'acquisition.json').write_text(json.dumps(acquisition)+'\n')
    return root


class SavedArrowTests(unittest.TestCase):
    def test_hold_before_clearance_and_straight_heading(self):
        with tempfile.TemporaryDirectory() as temp:
            result=analysis.measure(write_fixture(temp))
            self.assertEqual([r['frame'] for r in result['lawfully_occupied_frames']],[1,2])
            self.assertEqual(result['ego_past_stop_line_during_occupancy_frames'],[])
            self.assertEqual(result['observed_heading_change_deg'],0)
    def test_past_line_while_occupied_is_measured(self):
        with tempfile.TemporaryDirectory() as temp:
            path=write_fixture(temp)
            rows=[json.loads(line) for line in (path/'participant-history.jsonl').read_text().splitlines()]
            rows[4]['participants']=rows[2]['participants']
            source=path/'participant-history.jsonl';source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            acquisition=json.loads((path/'acquisition.json').read_text())
            acquisition[source.name]['sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            self.assertEqual(analysis.measure(path)['ego_past_stop_line_during_occupancy_frames'],[4])
    def test_stale_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=write_fixture(temp)
            (path/'intersection-context.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'stale original Native source'):
                analysis.measure(path)
    def test_extra_green_indication_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=write_fixture(temp)
            rows=[json.loads(line) for line in (path/'signal-head-history.jsonl').read_text().splitlines()]
            rows[5]['aspect']['illuminated_indications'].append({'color':'green','shape':'arrow','direction':'left'})
            source=path/'signal-head-history.jsonl';source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            acquisition=json.loads((path/'acquisition.json').read_text())
            acquisition[source.name]['sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            result=analysis.measure(path)
            self.assertIn(5,result['entry_without_verified_arrow_frames'])


if __name__=='__main__':unittest.main()
