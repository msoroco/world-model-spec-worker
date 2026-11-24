import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from carla_native_adapter import CarlaNativeAdapter


class Actor:
    def __init__(self,id):
        self.id=id
        self.controls=[]
        self.destroyed=False
    def apply_control(self,value):
        self.controls.append(value)
    def destroy(self):
        self.destroyed=True


class World:
    def __init__(self):
        self.actors=[]
        self.map=SimpleNamespace(to_opendrive=lambda:'original map')
    def get_map(self):
        return self.map
    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True,fixed_delta_seconds=.05)
    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name:name)
    def try_spawn_actor(self,blueprint,transform):
        actor=Actor(10+len(self.actors));self.actors.append(actor);return actor


class AdapterTests(unittest.TestCase):
    def test_reviewed_spawn_and_case_control_source(self):
        world=World()
        transform={'location':[0,0,0],'rotation':[0,0,0]}
        rows=[{'start_frame':0,'end_frame':899,'throttle':.2,'brake':0,'steer':0}]
        survey={'actor_sources':{name:{'blueprint_id':'vehicle.test','transform':transform}
                                 for name in ('ego','other')},
                'camera_sources':{name:{'mount':transform,'image_size_x':4,'image_size_y':4,'fov':90}
                                  for name in ('front','rear','left','right')},
                'control_schedules':{name:{'precedence':rows} for name in ('ego','other')},
                'governing_signal_actor_id':42}
        carla=SimpleNamespace(Transform=lambda loc,rot:(loc,rot),
                             Location=lambda *v:v,Rotation=lambda *v:v,
                             VehicleControl=lambda **v:v)
        adapter=CarlaNativeAdapter(SimpleNamespace(get_world=lambda:world),carla,survey)
        adapter.verify_map(survey,b'original map')
        handles=adapter.spawn_actors(survey,'exact__precedence')
        adapter.request_controls(handles,'exact__precedence',0)
        self.assertEqual(handles['ego'].controls[0]['throttle'],.2)
        self.assertEqual(handles['other'].controls[0]['brake'],0)
        with self.assertRaisesRegex(ValueError,'control schedule missing'):
            adapter.request_controls(handles,'exact__advance',0)
        with self.assertRaisesRegex(ValueError,'OpenDRIVE readback differs'):
            adapter.verify_map(survey,b'changed map')
        survey['control_schedules']['ego']['precedence'] = []
        with self.assertRaisesRegex(ValueError,'schedule gap'):
            adapter.request_controls(handles,'exact__precedence',0)


if __name__=='__main__':
    unittest.main()
