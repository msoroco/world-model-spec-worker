import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('following_measurements',ROOT/'following_measurements.py')
measure=importlib.util.module_from_spec(spec);spec.loader.exec_module(measure)
def body(x,y):return [[x-1,y-1],[x+1,y-1],[x+1,y+1],[x-1,y+1]]
class Tests(unittest.TestCase):
 def fixture(self,root,gap=8,wet=False):
  context={'native_map_id':'TownX','highway_id':1,'road_id':7,'following_lane_id':-1,'target_lane_id':-2,'hill_crest_source':'native-elevation-profile','lane_geometry_source':'native-waypoints','surface_source':'weather-and-road-review','traffic_source':'native-actor-inventory','route_source':'native-waypoints','following_forward_xy':[1,0]}
  (root/'road_context.json').write_text(json.dumps(context))
  history=[]
  for i,(x,y,change) in enumerate(((0,0,False),(2,0,False),(4,4,True))):
   history.append({'frame':100+i,'time_s':1+i*.05,'road_id':7,'ego':{'actor_id':11,'lane_id':-2 if change else -1,'body_vertices_xy_m':body(x,y),'velocity_mps':[5,0,0],'speed_source':'actor.get_velocity'},'lead':{'actor_id':22,'lane_id':-1,'body_vertices_xy_m':body(x+gap,0),'velocity_mps':[4,0,0],'speed_source':'actor.get_velocity','brake_applied':i==1},'surface_condition':'wet' if wet else 'dry','traffic_actor_ids':[11,22,33],'lane_change_started':change})
  frames=[{'video_frame':i,'carla_frame':row['frame'],'time_s':row['time_s']} for i,row in enumerate(history)]
  (root/'vehicle_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in history))
  (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
 def test_gap_speed_surface_and_following_end(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,8);wide=measure.analyze(root)
   self.assertEqual(wide['minimum_sampled_body_gap_m'],6)
   self.assertEqual(wide['following_end']['frame'],101)
   self.assertEqual(wide['first_lane_change']['frame'],102)
   self.assertEqual(wide['samples'][1]['lead_speed_mps'],4)
   self.assertTrue(wide['samples'][1]['lead_brake'])
   self.fixture(root,5,True);narrow=measure.analyze(root)
   self.assertEqual(narrow['minimum_sampled_body_gap_m'],3)
   self.assertEqual(narrow['samples'][0]['surface_condition'],'wet')
   self.assertEqual(narrow['legal_conclusion'],'unresolved')
 def test_stale_join_and_missing_native_velocity_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   frames=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()]
   frames[1]['carla_frame']=999
   (root/'video_frames.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
   self.fixture(root)
   rows=[json.loads(s) for s in (root/'vehicle_history.jsonl').read_text().splitlines()]
   rows[1]['lead']['speed_source']='controller_target'
   (root/'vehicle_history.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in rows))
   with self.assertRaisesRegex(ValueError,'Native velocities'):measure.analyze(root)
 def test_no_following_before_lane_change_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   rows=[json.loads(s) for s in (root/'vehicle_history.jsonl').read_text().splitlines()]
   for row in rows:row['lead']['body_vertices_xy_m']=body(-10,0)
   (root/'vehicle_history.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in rows))
   with self.assertRaisesRegex(ValueError,'No observed following'):measure.analyze(root)
if __name__=='__main__':unittest.main()
