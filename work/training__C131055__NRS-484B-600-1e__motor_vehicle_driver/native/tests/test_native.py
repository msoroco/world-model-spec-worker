import json
import tempfile
import unittest
from pathlib import Path
from geometry import ARC_M, check as geometry_check, open_drive
from runner import check as runner_check, survey
from measure import measure

class FakePoint:
    def __init__(self,x,y,z):self.x,self.y,self.z=x,y,z
class FakeWaypoint:
    def __init__(self,road,lane,s):
        self.road_id,self.lane_id,self.s=road,lane,s
        self.transform=type('T',(),{'location':FakePoint(s, -500, 0)})()
class FakeMap:
    def get_waypoint_xodr(self,road,lane,s):return FakeWaypoint(road,lane,s)
class FakeWorld:
    def get_map(self):return FakeMap()

class NativeDraft(unittest.TestCase):
    def test_geometry(self):
        g=geometry_check()
        self.assertEqual(g['lane_ids'],[-1,-2])
        self.assertGreater(g['arc_length_m'],700)
    def test_capture_plan_and_survey(self):
        p=runner_check()
        self.assertEqual(p['frames'],600)
        self.assertEqual(len(p['cameras']),4)
        self.assertEqual(len(survey(FakeWorld(),None)),8)
    def test_source_bound_speed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            survey_path=root/'survey.json'
            survey_path.write_text(json.dumps(survey(FakeWorld(),None)))
            history=root/'history.jsonl'
            rows=[]
            for i in range(600):
                road=1 if i<100 else 2
                speed=30 if i<400 else 38
                rows.append({'video_frame':i,'native_frame':i+100,'time_s':i/20,'subject_id':8,'position_xyz_m':[i,-500,0],'velocity_xyz_mps':[speed,0,0],'road_id':road,'lane_id':-2})
            history.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            m=measure(history,survey_path)
            self.assertEqual(m['first_exit_road_frame'],100)
            self.assertEqual(m['samples_above_80_mph'],200)
            self.assertIsNone(m['legal_conclusion'])
            for row in rows:
                row['velocity_xyz_mps'] = [35.7632, 0, 0]
            history.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            at = measure(history, survey_path)
            self.assertEqual(at['maximum_full_trace_mph'], 80.0)
            self.assertEqual(at['samples_above_80_mph'], 0)
            self.assertEqual(at['samples_at_80_mph'], 600)
            rows[599]['velocity_xyz_mps'] = [35.763201, 0, 0]
            history.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            self.assertEqual(measure(history, survey_path)['samples_above_80_mph'], 1)
            rows[300].pop('velocity_xyz_mps')
            history.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'velocity vector missing'):
                measure(history,survey_path)
