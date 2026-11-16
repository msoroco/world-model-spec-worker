import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('stop_reference_measurements',ROOT/'stop_reference_measurements.py')
import sys
sys.path.insert(0,str(ROOT))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def write_rows(path,rows):path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
def body(x):return [[x-1,-1],[x-1,1],[x+1,1],[x+1,-1]]
class StopReferenceTests(unittest.TestCase):
 def fixture(self,root,line=True,halt_x=5):
  ctx={'native_map_id':'TownFixture','intersection_id':44,'approach_road_id':7,'approach_lane_id':-1,'native_stop_sign_id':25,'sign_governance_source':'Native trigger readback','junction_source':'reviewed polygon','near_side_crosswalk_exists':False,'crosswalk_absence_source':'original map and sidewalk inventory','stop_line_exists':line,'approach_forward_xy':[1,0],'intersection_polygon_xy_m':[[20,-5],[30,-5],[30,5],[20,5]],'stop_line_marking_source':'original marking evidence','stop_line_segment_xy_m':[[10,-5],[10,5]],'sight_observer_source':'original per-frame ray packet','approaching_traffic_source':'original intersecting-road actor inventory'}
  (root/'approach_context.json').write_text(json.dumps(ctx))
  xs=[0,halt_x,11,22];rows=[{'frame':100+i,'time_s':1+i*.05,'road_id':7,'lane_id':-1,'stop_sign_id':25,'ego_speed_mps':0 if i==1 else 2,'ego_body_vertices_xy_m':body(x)} for i,x in enumerate(xs)]
  write_rows(root/'stop_history.jsonl',rows);write_rows(root/'video_frames.jsonl',[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)])
  write_rows(root/'sight_history.jsonl',[{'frame':r['frame'],'time_s':r['time_s'],'approaching_traffic_ids':[42],'visible_approaching_traffic_ids':[] if i<2 else [42]} for i,r in enumerate(rows)])
 def test_marked_line_branch_and_inside_negative(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   result=mod.analyze(root);self.assertEqual(result['selected_reference'],'marked_stop_line');self.assertTrue(result['halt_before_reference_and_junction_observed']);self.assertIsNone(result['first_observed_view'])
   self.fixture(root,halt_x=11);self.assertFalse(mod.analyze(root)['halt_before_reference_and_junction_observed'])
 def test_sight_branch_and_missing_source_rejection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,line=False)
   result=mod.analyze(root);self.assertEqual(result['selected_reference'],'first_observed_view');self.assertTrue(result['halt_before_reference_and_junction_observed']);self.assertEqual(result['first_observed_view']['visible_ids'],[42]);self.assertEqual(result['legal_conclusion'],'unresolved')
   p=root/'sight_history.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()];rows[2]['visible_approaching_traffic_ids']=[99];write_rows(p,rows)
   with self.assertRaisesRegex(ValueError,'inconsistent original'):mod.analyze(root)
   p.unlink()
   with self.assertRaisesRegex(ValueError,'Missing original source'):mod.analyze(root)
 def test_crosswalk_precedence_and_stale_join_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   p=root/'approach_context.json';ctx=json.loads(p.read_text());ctx['near_side_crosswalk_exists']=True;p.write_text(json.dumps(ctx))
   with self.assertRaisesRegex(ValueError,'No-crosswalk branch'):mod.analyze(root)
   self.fixture(root,line=False);p=root/'sight_history.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()];rows[2]['frame']=999;write_rows(p,rows)
   with self.assertRaisesRegex(ValueError,'sight frame join'):mod.analyze(root)
if __name__=='__main__':unittest.main()
