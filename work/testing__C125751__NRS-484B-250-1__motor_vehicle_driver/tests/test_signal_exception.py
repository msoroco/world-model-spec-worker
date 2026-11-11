import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measurement=load('crossing_precedence');signal=load('signal_control')
def body(x,y):return [[x-1,y-1],[x+1,y-1],[x+1,y+1],[x-1,y+1]]
class Tests(unittest.TestCase):
 def fixture(self,root,state='Red'):
  ctx={'native_map_id':'TownX','intersection_id':5,'ego_highway_id':1,'other_highway_id':2,'ego_road_id':11,'other_road_id':22,'crossing_geometry_source':'native-junction','all_entrances_source':'native-map','official_device_inventory_source':'native-and-camera','median_spacing_source':'native-map','same_statutory_crossing':True,'official_device_controls_crossing':True,'governing_signal_state':state,'opposite_approach_with_left_turn':False,'intersection_polygon_xy_m':[[0,0],[10,0],[10,10],[0,10]]}
  (root/'junction_context.json').write_text(json.dumps(ctx))
  positions=[((-4,5),(14,5)),((-4,5),(5,5)),((5,5),(5,5))]
  rows=[{'frame':100+i,'time_s':i*.05,'ego':{'intersection_id':5,'road_id':11,'body_vertices_xy_m':body(*ego)},'other':{'intersection_id':5,'road_id':22,'body_vertices_xy_m':body(*other)}} for i,(ego,other) in enumerate(positions)]
  frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
  (root/'crossing_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
 def test_active_signal_excludes_subsection_one_and_off_needs_four(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,'Red');r=measurement.analyze(root);self.assertTrue(r['other_enters_before_ego']);self.assertEqual(r['subsection_1_applicability'],'excluded_by_official_device')
   self.fixture(root,'Off');self.assertEqual(measurement.analyze(root)['subsection_1_applicability'],'subsection_4_qualification_required')
 def test_unknown_status_and_stale_frame_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);ctx=json.loads((root/'junction_context.json').read_text());ctx.pop('official_device_controls_crossing');(root/'junction_context.json').write_text(json.dumps(ctx))
   with self.assertRaisesRegex(ValueError,'control status'):measurement.analyze(root)
   self.fixture(root);frames=[json.loads(x) for x in (root/'video_frames.jsonl').read_text().splitlines()];frames[2]['carla_frame']=999;(root/'video_frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measurement.analyze(root)
 def test_native_signal_selection(self):
  light=NS(id=8,get_affected_lane_waypoints=lambda:[NS(road_id=11,lane_id=-1)],get_state=lambda:'Red')
  world=NS(get_actors=lambda:NS(filter=lambda q:[light]))
  self.assertEqual(signal.governing_signal(world,11,-1)['subsection_1_applicability'],'excluded_by_official_device')
  self.assertEqual(signal.governing_signal(world,11,-1)['signal_actor_id'],8)
  with self.assertRaisesRegex(ValueError,'Exactly one'):signal.governing_signal(world,11,1)
if __name__=='__main__':unittest.main()
