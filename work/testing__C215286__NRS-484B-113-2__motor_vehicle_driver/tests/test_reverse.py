import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('crosswalk_reverse');control=load('reverse_control');comparison=load('comparison_audit');route=load('reverse_route')
def body(x):return [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]]
class Tests(unittest.TestCase):
 def fixture(self,root,on_crosswalk=True):
  for name in ('district.txt','geometry.txt','marking.txt'):
   (root/name).write_text('Synthetic '+name+' source')
  ref=lambda name:{'path':name,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()}
  packet={'native_map_id':'TownX','road_id':7,'crosswalk_id':55,
          'district_kind':'residence','district_review_basis':'synthetic fixture only',
          'crosswalk_review_basis':'synthetic fixture only','reviewer':'CPU fixture',
          'crosswalk_polygon_xy_m':[[8,-3],[12,-3],[12,3],[8,3]],
          'roadway_polygon_xy_m':[[0,-2],[25,-2],[25,2],[0,2]],
          'district_source':ref('district.txt'),
          'crosswalk_geometry_source':ref('geometry.txt'),
          'crosswalk_marking_source':ref('marking.txt')}
  (root/'site_packet.json').write_text(json.dumps(packet))
  ctx={'native_map_id':'TownX','road_id':7,'crosswalk_id':55,'crosswalk_geometry_source':'native-map','crosswalk_camera_source':'front-original','reverse_route_source':'native-waypoints','residence_district_source':'district-map','crosswalk_polygon_xy_m':[[8,-3],[12,-3],[12,3],[8,3]]}
  (root/'crosswalk_context.json').write_text(json.dumps(ctx))
  xs=[16,10,6] if on_crosswalk else [16,15,14]
  rows=[{'frame':100+i,'time_s':1+i*.05,'road_id':7,'crosswalk_id':55,'native_reverse':True,'ego_forward_xy':[1,0],'ego_body_vertices_xy_m':body(x)} for i,x in enumerate(xs)]
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
 def test_reverse_gear_without_backward_motion_does_not_count(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   rows=[json.loads(s) for s in (root/'reverse_history.jsonl').read_text().splitlines()]
   rows[1]['ego_forward_xy']=[-1,0]
   rows[2]['ego_forward_xy']=[-1,0]
   (root/'reverse_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   report=measure.analyze(root)
   self.assertFalse(report['backward_motion_observed'])
   self.assertFalse(report['reverse_body_on_or_over_crosswalk'])
   self.fixture(root);rows=[json.loads(s) for s in (root/'reverse_history.jsonl').read_text().splitlines()]
   rows[1].pop('ego_forward_xy')
   (root/'reverse_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   with self.assertRaisesRegex(ValueError,'heading'):measure.analyze(root)
 def test_new_reverse_state_at_overlap_does_not_claim_prior_interval(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   rows=[json.loads(s) for s in (root/'reverse_history.jsonl').read_text().splitlines()]
   rows[0]['native_reverse']=False
   (root/'reverse_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   report=measure.analyze(root)
   self.assertFalse(report['reverse_body_on_or_over_crosswalk'])
   self.assertTrue(report['backward_motion_observed'])
 def test_saved_measurement_rejects_stale_site_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   self.assertIn('marking.txt',measure.analyze(root)['sources'])
   packet=json.loads((root/'site_packet.json').read_text())
   prepared=route.prepare_reviewed_pair(packet,root,body(16),[1,0],
                                         over_distance_m=6,short_distance_m=2,
                                         native_map_id='TownX',road_id=7,crosswalk_id=55)
   self.assertEqual(prepared['targets']['over_distance_m'],6)
   (root/'marking.txt').write_text('Changed marking source')
   with self.assertRaisesRegex(ValueError,'Stale crosswalk_marking source hash'):
    measure.analyze(root)
   self.fixture(root);(root/'site_packet.json').unlink()
   with self.assertRaisesRegex(ValueError,'Missing original source: site_packet.json'):
    measure.analyze(root)
 def test_paired_complete_body_targets_and_reverse_controller(self):
  crossing=[[8,-3],[12,-3],[12,3],[8,3]]
  plan=route.validate_pair(body(16),[1,0],crossing,
                           over_distance_m=6,short_distance_m=2)
  self.assertTrue(plan['start_body_clear'])
  over=route.ReverseTargetController([16,0],[1,0],6)
  short=route.ReverseTargetController([16,0],[1,0],2)
  self.assertTrue(over.step([16,0],0)['reverse'])
  self.assertGreater(over.step([16,0],0)['throttle'],0)
  self.assertTrue(over.step([10,0],0)['target_reached'])
  self.assertTrue(short.step([14,0],0)['target_reached'])
  approach_brake=short.step([15,0],2)
  self.assertEqual(approach_brake['brake'],1)
  self.assertFalse(approach_brake['target_reached'])
  with self.assertRaisesRegex(ValueError,'Short target body overlaps'):
   route.validate_pair(body(16),[1,0],crossing,
                       over_distance_m=6,short_distance_m=5)
  with self.assertRaisesRegex(ValueError,'Over target body misses'):
   route.validate_pair(body(16),[1,0],crossing,
                       over_distance_m=2,short_distance_m=1)
 def test_real_native_reverse_request_and_restore(self):
  original=NS(throttle=0,brake=0,reverse=False)
  vehicle=NS(control=original)
  vehicle.get_control=lambda:vehicle.control
  vehicle.apply_control=lambda c:setattr(vehicle,'control',c)
  world=NS(tick=lambda:None)
  with control.reverse_vehicle(world,vehicle,NS,throttle=.2):self.assertTrue(vehicle.get_control().reverse)
  self.assertFalse(vehicle.get_control().reverse)
 def test_independent_boundary_comparison(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);over=root/'over';short=root/'short';over.mkdir();short.mkdir()
   self.fixture(over,True);self.fixture(short,False)
   self.assertEqual(comparison.audit(over,short)['frame_count'],3)
   ctx=json.loads((short/'crosswalk_context.json').read_text());ctx['crosswalk_camera_source']='other-original'
   (short/'crosswalk_context.json').write_text(json.dumps(ctx))
   with self.assertRaisesRegex(ValueError,'crosswalk context differs'):comparison.audit(over,short)
   self.fixture(short,True)
   with self.assertRaisesRegex(ValueError,'Short case body overlaps'):comparison.audit(over,short)
   self.fixture(short,False)
   (short/'marking.txt').write_text('Different synthetic marking source')
   packet=json.loads((short/'site_packet.json').read_text())
   packet['crosswalk_marking_source']['sha256']=hashlib.sha256((short/'marking.txt').read_bytes()).hexdigest()
   (short/'site_packet.json').write_text(json.dumps(packet))
   with self.assertRaisesRegex(ValueError,'site source differs'):comparison.audit(over,short)
if __name__=='__main__':unittest.main()
