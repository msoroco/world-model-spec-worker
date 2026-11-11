import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('inoperative_stop');control=load('signal_control')
def body(x):return [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]]
class Tests(unittest.TestCase):
 def fixture(self,root,reference='marked_stop_line',other_inside=True):
  ctx={'native_map_id':'TownX','intersection_id':44,'all_entrance_signal_source':'native-map-and-video','installed_uncovered_source':'all-head-video','stop_reference_source':'native-markings','junction_source':'native-map','other_vehicle_source':'native-actor','installed_uncovered':True,'entrance_signal_ids':[1,2],'stop_reference_kind':reference,'marked_stop_line_present':reference=='marked_stop_line','near_crosswalk_present':reference=='near_crosswalk','intersection_polygon_xy_m':[[10,-5],[20,-5],[20,5],[10,5]]}
  (root/'junction_context.json').write_text(json.dumps(ctx))
  rows=[]
  for i,(x,speed) in enumerate(((0,2),(0,0),(12,2))):
   rows.append({'frame':100+i,'time_s':1+i*.05,'entrance_signal_states':{'1':'Off','2':'Off'},'ego_body_vertices_xy_m':body(x),'other_body_vertices_xy_m':body(13 if other_inside else 25),'ego_speed_mps':speed,'ego_complete_body_before_stop_reference':i<2,'other_completed_stop':False})
  frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
  (root/'entry_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
 def test_stop_reference_and_priority(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for reference in ('marked_stop_line','near_crosswalk','nearest_view'):
    self.fixture(root,reference);r=measure.analyze(root);self.assertTrue(r['observed_pre_entry_stop']);self.assertTrue(r['other_priority_at_entry']);self.assertEqual(r['stop_reference_kind'],reference)
   self.fixture(root,other_inside=False);self.assertFalse(measure.analyze(root)['other_priority_at_entry'])
 def test_operating_head_and_stale_frame_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);rows=[json.loads(s) for s in (root/'entry_history.jsonl').read_text().splitlines()];rows[1]['entrance_signal_states']['2']='Red';(root/'entry_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   with self.assertRaisesRegex(ValueError,'signals not observed Off'):measure.analyze(root)
   self.fixture(root);frames=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()];frames[1]['carla_frame']=999;(root/'video_frames.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
 def test_native_all_entrance_off_and_restore(self):
  class Actors(list):
   def filter(self,p):return self
  class Light:
   def __init__(self,ident,road):self.id,self.road,self.state=ident,road,'Red'
   def get_affected_lane_waypoints(self):return [NS(road_id=self.road,lane_id=-1)]
   def get_state(self):return self.state
   def set_state(self,s):self.state=s
   def freeze(self,s):self.frozen=s
  lights=[Light(1,7),Light(2,8)];world=NS(get_actors=lambda:Actors(lights),tick=lambda:None)
  chosen=control.find_entrance_lights(world,[(7,-1),(8,-1)])
  with control.request_all_off(world,chosen,NS(Off='Off')):self.assertTrue(all(l.state=='Off' for l in lights))
  self.assertTrue(all(l.state=='Red' for l in lights))
if __name__=='__main__':unittest.main()
