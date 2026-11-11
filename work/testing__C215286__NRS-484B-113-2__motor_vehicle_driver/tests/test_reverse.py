import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('crosswalk_reverse');control=load('reverse_control')
def body(x):return [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]]
class Tests(unittest.TestCase):
 def fixture(self,root,on_crosswalk=True):
  ctx={'native_map_id':'TownX','road_id':7,'crosswalk_id':55,'crosswalk_geometry_source':'native-map','crosswalk_camera_source':'front-original','reverse_route_source':'native-waypoints','residence_district_source':'district-map','crosswalk_polygon_xy_m':[[8,-3],[12,-3],[12,3],[8,3]]}
  (root/'crosswalk_context.json').write_text(json.dumps(ctx))
  xs=[16,10,6] if on_crosswalk else [20,18,16]
  rows=[{'frame':100+i,'time_s':1+i*.05,'road_id':7,'crosswalk_id':55,'native_reverse':i>0,'ego_body_vertices_xy_m':body(x)} for i,x in enumerate(xs)]
  frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
  (root/'reverse_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
 def test_reverse_on_and_over_crosswalk(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);r=measure.analyze(root);self.assertTrue(r['reverse_body_on_or_over_crosswalk']);self.assertTrue(r['reverse_body_fully_over_crosswalk'])
   self.fixture(root,False);self.assertFalse(measure.analyze(root)['reverse_body_on_or_over_crosswalk'])
 def test_wrong_id_and_stale_frame_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);rows=[json.loads(s) for s in (root/'reverse_history.jsonl').read_text().splitlines()];rows[1]['crosswalk_id']=99;(root/'reverse_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   with self.assertRaisesRegex(ValueError,'identity'):measure.analyze(root)
   self.fixture(root);frames=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()];frames[1]['carla_frame']=999;(root/'video_frames.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
 def test_real_native_reverse_request_and_restore(self):
  original=NS(throttle=0,brake=0,reverse=False)
  vehicle=NS(control=original)
  vehicle.get_control=lambda:vehicle.control
  vehicle.apply_control=lambda c:setattr(vehicle,'control',c)
  world=NS(tick=lambda:None)
  with control.reverse_vehicle(world,vehicle,NS,throttle=.2):self.assertTrue(vehicle.get_control().reverse)
  self.assertFalse(vehicle.get_control().reverse)
if __name__=='__main__':unittest.main()
