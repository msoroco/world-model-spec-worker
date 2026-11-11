import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('caravan_spacing');construct=load('caravan_construction')
def body(x):return [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]]
class Tests(unittest.TestCase):
 def fixture(self,root,spacing=10):
  ctx={'native_map_id':'TownX','highway_id':44,'road_id':7,'business_district_source':'district-map-review','caravan_membership_source':'route-manifest','route_source':'native-waypoints','lane_source':'native-map','outside_business_district':True,'caravan_or_motorcade':True,'roadway_polygon_xy_m':[[0,-5],[80,-5],[80,5],[0,5]],'road_forward_xy':[1,0]}
  (root/'road_context.json').write_text(json.dumps(ctx))
  rows=[]
  for i in range(2):
   members=[{'actor_id':j+1,'body_vertices_xy_m':body(10+j*spacing+i)} for j in range(3)]
   rows.append({'frame':100+i,'time_s':1+i*.05,'road_id':7,'caravan_members':members,'entering_vehicle':{'actor_id':9,'body_vertices_xy_m':body(10+spacing/2+i)}})
  frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
  (root/'caravan_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
 def test_gap_changes_and_no_legal_cutoff(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,10);large=measure.analyze(root);self.fixture(root,5);small=measure.analyze(root)
   self.assertGreater(large['samples'][0]['gaps'][0]['body_clearance_m'],small['samples'][0]['gaps'][0]['body_clearance_m']);self.assertEqual(large['legal_conclusion'],'unresolved')
 def test_activation_and_frame_source_required(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);ctx=json.loads((root/'road_context.json').read_text());ctx['outside_business_district']=False;(root/'road_context.json').write_text(json.dumps(ctx))
   with self.assertRaisesRegex(ValueError,'activation'):measure.analyze(root)
   self.fixture(root);frames=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()];frames[1]['carla_frame']=999;(root/'video_frames.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
 def test_three_real_vehicle_spawns_and_cleanup(self):
  destroyed=[]
  def actor(x):return NS(get_location=lambda:NS(x=x,y=0),destroy=lambda:destroyed.append(x))
  it=iter([actor(0),actor(10),actor(20)]);world=NS(try_spawn_actor=lambda bp,tr:next(it))
  with construct.spawn_caravan(world,[('car','t')]*3) as actors:self.assertEqual(len(actors),3)
  self.assertEqual(destroyed,[20,10,0])
if __name__=='__main__':unittest.main()
