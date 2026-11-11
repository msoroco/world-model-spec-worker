import importlib.util,io,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capture_sources',ROOT/'capture_sources.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class FakeActor:
 def __init__(self,ident,x,speed):
  self.id=ident;self.x=x;self.speed=speed;self.calls=[]
  self.bounding_box=NS(get_world_vertices=lambda transform:[NS(x=self.x+dx,y=dy) for dx,dy in ((-1,-1),(1,-1),(1,1),(-1,1))])
 def get_transform(self):self.calls.append('get_transform');return NS(rotation=NS(yaw=0.0))
 def get_velocity(self):self.calls.append('get_velocity');return NS(x=self.speed,y=0.0,z=0.0)
 def get_control(self):return NS(brake=0)
 def get_location(self):return NS(x=self.x,y=0,z=0)
class Tests(unittest.TestCase):
 def test_native_original_body_velocity_and_four_camera_join_claim(self):
  ego,lead=FakeActor(11,0,5),FakeActor(22,10,4)
  mapped=[];frame_map=NS(append=lambda frame,time:mapped.append((frame,time)) or {'video_frame':0})
  streams=[io.StringIO() for _ in range(3)]
  snapshot=NS(frame=100,timestamp=NS(elapsed_seconds=1.0))
  result=module.record_sample(frame_map,*streams,snapshot,ego,lead,road_id=7,ego_lane_id=-1,lead_lane_id=-1,surface_condition='dry',traffic_actor_ids=[11,22],lane_change_started=False)
  self.assertEqual(mapped,[(100,1.0)])
  self.assertEqual(result['history']['lead']['velocity_mps'],[4.,0.,0.])
  self.assertEqual(len(result['history']['ego']['body_vertices_xy_m']),4)
  self.assertIn('get_velocity',ego.calls);self.assertIn('get_velocity',lead.calls)
  self.assertEqual(len(result['evidence']['source_camera_names']),4)
  self.assertTrue(all(s.getvalue().endswith('\n') for s in streams))
 def test_missing_native_body_rejects_before_frame_map_append(self):
  ego,lead=FakeActor(11,0,5),FakeActor(22,10,4)
  ego.bounding_box=NS(get_world_vertices=lambda transform:[])
  mapped=[];frame_map=NS(append=lambda *a:mapped.append(a))
  with self.assertRaisesRegex(ValueError,'body vertices'):
   module.record_sample(frame_map,io.StringIO(),io.StringIO(),io.StringIO(),NS(frame=100,timestamp=NS(elapsed_seconds=1.0)),ego,lead,road_id=7,ego_lane_id=-1,lead_lane_id=-1,surface_condition='dry',traffic_actor_ids=[11,22],lane_change_started=False)
  self.assertEqual(mapped,[])
if __name__=='__main__':unittest.main()
