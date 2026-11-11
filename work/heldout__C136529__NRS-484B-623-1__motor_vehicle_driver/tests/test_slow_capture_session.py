import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
folder=Path(__file__).resolve().parents[1]
runtime=folder.parents[1]/'runtime'
sys.path.insert(0,str(folder));sys.path.insert(0,str(runtime));sys.path.insert(0,str(runtime/'scenario_pipeline'))
from slow_capture_session import SlowCaptureSession
from slow_finalizer import analyze

def point(x,y,z=0):return SimpleNamespace(x=x,y=y,z=z)
class Actor:
    def __init__(self,id,x,y):
        self.id=id;self.type_id='vehicle.test';self.is_alive=True;self.x=x;self.y=y
        self.bounding_box=SimpleNamespace(get_world_vertices=lambda t:[point(x+dx,y+dy,z) for dx in (-1,1) for dy in (-1,1) for z in (0,1)])
    def get_transform(self):return SimpleNamespace(location=point(self.x,self.y))
    def get_velocity(self):return point(3,0)
class Pipeline:
    def __init__(self,root):self.trace=(root/'trace.jsonl').open('x')
    def capture(self,frame,time_s):
        row={'frame':frame,'time_s':time_s}
        self.trace.write(json.dumps(row)+'\n');self.trace.flush();return row
    def close(self):self.trace.close()
class CaptureTest(unittest.TestCase):
    def test_original_sources_join_saved_finalizer(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'config.json').write_text(json.dumps({'law_id':'NRS-484B-623-1','cell_id':'C136529',
                'actor':'motor_vehicle_driver','selected_case_id':'heldout__C136529__NRS-484B-623-1__motor_vehicle_driver__slow_for_obstruction',
                'case':{'recording_description':{'channels':[]}}}))
            pipeline=Pipeline(root)
            ego,follower,opposing,obstruction=[Actor(i,*xy) for i,xy in enumerate([(0,0),(0,-20),(0,60),(0,5)],1)]
            with SlowCaptureSession(root,pipeline,ego,follower,opposing,obstruction,None,
                                    {'case_branch':'slow_for_obstruction'}) as session:
                for i in range(3):
                    session.capture(100+i,i*.05)
                    ego.y+=.15;follower.y+=.2;opposing.y-=.4
            pipeline.close()
            report=analyze(root)
            self.assertEqual(len(report['measurements']['slow_speed_observation']['value']['samples']),3)
            self.assertTrue(json.loads((root/'prop_state.jsonl').read_text().splitlines()[0])['obstruction_geometry']['vertices_xyz'])
    def test_missing_physical_prop_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'requires physical prop'):
                SlowCaptureSession(Path(temp),None,Actor(1,0,0),Actor(2,0,-20),Actor(3,0,60),None,None,
                                   {'case_branch':'slow_for_obstruction'})
if __name__=='__main__':unittest.main()
