import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('one_way_measurements');native=load('native_one_way')
def body(x):return [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]]
class Tests(unittest.TestCase):
 def fixture(self,root,reverse=False):
  ctx={'native_map_id':'TownX','highway_id':44,'road_id':5,'one_way_designation_source':'authority-map','direction_sign_source':'sign-camera','lane_geometry_source':'native-map','travel_route_source':'waypoint-chain','driving_lane_ids':[-1,-2],'designated_forward_xy':[1,0],'one_way_roadway_polygon_xy_m':[[0,-4],[30,-4],[30,4],[0,4]]}
  (root/'road_context.json').write_text(json.dumps(ctx))
  xs=[20,15,10] if reverse else [10,15,20]
  rows=[{'frame':100+i,'time_s':1+i*.05,'road_id':5,'lane_id':-1,'ego_body_vertices_xy_m':body(x),'ego_forward_xy':[-1,0] if reverse else [1,0]} for i,x in enumerate(xs)]
  frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
  (root/'travel_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
 def test_designated_and_wrong_direction(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);self.assertTrue(measure.analyze(root)['all_steps_designated_direction'])
   self.fixture(root,True);r=measure.analyze(root);self.assertFalse(r['all_steps_designated_direction']);self.assertLess(r['samples'][0]['heading_alignment'],0)
 def test_wrong_lane_and_stale_frame_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);rows=[json.loads(x) for x in (root/'travel_history.jsonl').read_text().splitlines()];rows[1]['lane_id']=1;(root/'travel_history.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
   with self.assertRaisesRegex(ValueError,'one-way lanes'):measure.analyze(root)
   self.fixture(root);frames=[json.loads(x) for x in (root/'video_frames.jsonl').read_text().splitlines()];frames[1]['carla_frame']=900;(root/'video_frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
 def test_native_multilane_inventory(self):
  wps=[NS(road_id=5,lane_id=i,lane_type='Driving') for i in (-1,-2)]
  world=NS(get_map=lambda:NS(generate_waypoints=lambda spacing:wps))
  self.assertEqual(native.verify_multilane_one_way(world,5,[-1,-2])['selected_lane_ids'],[-2,-1])
  wps.append(NS(road_id=5,lane_id=1,lane_type='Driving'))
  with self.assertRaisesRegex(ValueError,'opposing'):native.verify_multilane_one_way(world,5,[-1,1])
if __name__=='__main__':unittest.main()
