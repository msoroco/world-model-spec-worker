import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('uturn_measurements');construction=load('barrier_construction')
def body(x,y):return [[x+dx,y+dy] for dx,dy in ((-1,-1),(-1,1),(1,1),(1,-1))]
class Tests(unittest.TestCase):
 def fixture(self,root,multiple=False,opening_x=15):
  ctx={'native_map_id':'TownX','divided_highway_source':'road-and-camera-review','roadway_boundaries_source':'native-map-and-body','opening_geometry_source':'native-divider-gap','barrier_actors_source':'native-world-vertices','other_vehicle_source':'native-actor-and-camera','public_authority_source':'source-review-required','uturn_route_source':'native-waypoints','right_hand_roadway_xy_m':[[0,-10],[30,-10],[30,-2],[0,-2]],'destination_roadway_xy_m':[[0,2],[30,2],[30,10],[0,10]],'dividing_space_xy_m':[[0,-2],[30,-2],[30,2],[0,2]],'opening_xy_m':[[10,-2],[20,-2],[20,2],[10,2]]}
  (root/'divider_context.json').write_text(json.dumps(ctx))
  gear=['forward','forward','reverse','forward','forward'] if multiple else ['forward']*5
  positions=[(0,-5,[1,0]),(opening_x,1,[1,0]),(opening_x,0,[0,1]),(15,3,[-.7,.7]),(15,5,[-1,0])] if multiple else [(0,-5,[1,0]),(12,-5,[1,0]),(opening_x,0,[0,1]),(15,3,[-.7,.7]),(15,5,[-1,0])]
  rows=[{'frame':100+i,'time_s':1+i*.05,'ego_body_vertices_xy_m':body(x,y),'other_body_vertices_xy_m':body(25,-5),'ego_forward_xy':heading,'ego_gear':gear[i]} for i,(x,y,heading) in enumerate(positions)]
  frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
  (root/'movement_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
 def test_uturn_and_multiple_movement(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);r=measure.analyze(root)
   self.assertEqual(abs(r['observed_turn_angle_degrees']),180);self.assertTrue(r['opening_traversed_observed']);self.assertFalse(r['any_body_overlap_outside_opening']);self.assertFalse(r['multiple_movement_observed'])
   self.fixture(root,True);self.assertTrue(measure.analyze(root)['reverse_motion_observed']);self.assertTrue(measure.analyze(root)['multiple_movement_observed'])
   self.fixture(root,False,5);self.assertTrue(measure.analyze(root)['any_body_overlap_outside_opening'])
 def test_stale_frame_and_missing_gear_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);frames=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()];frames[2]['carla_frame']=999;(root/'video_frames.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
   self.fixture(root);rows=[json.loads(s) for s in (root/'movement_history.jsonl').read_text().splitlines()];rows[2].pop('ego_gear');(root/'movement_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   with self.assertRaisesRegex(ValueError,'gear'):measure.analyze(root)
 def test_two_real_barrier_sections_and_cleanup(self):
  destroyed=[]
  def actor(xmin,xmax):
   vertices=[NS(x=x,y=y) for x,y in ((xmin,-2),(xmin,2),(xmax,2),(xmax,-2))]
   return NS(bounding_box=NS(get_world_vertices=lambda transform:vertices),get_transform=lambda:'t',destroy=lambda:destroyed.append(True))
  it=iter((actor(0,8),actor(22,30)));world=NS(try_spawn_actor=lambda bp,tr:next(it))
  with construction.spawn_barrier_opening(world,[('a','b'),('c','d')],[[10,-2],[20,-2],[20,2],[10,2]],(1,0)) as built:self.assertEqual(len(built['actors']),2)
  self.assertEqual(destroyed,[True,True])
if __name__=='__main__':unittest.main()
