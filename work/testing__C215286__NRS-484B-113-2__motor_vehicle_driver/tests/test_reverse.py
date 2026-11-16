import hashlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parents[1]/'runtime'/'scenario_pipeline'))
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('crosswalk_reverse');control=load('reverse_control');comparison=load('comparison_audit');route=load('reverse_route');runner=load('runner');finalizer=load('finalizer')
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
  rows=[{'frame':100+i,'time_s':1+i*.05,'road_id':7,'crosswalk_id':55,
         'native_reverse':True,'ego_forward_xy':[1,0],
         'ego_body_vertices_xy_m':body(x),'body_vertices_m':body(x),
         'heading_deg':0,'velocity_mps':[-1,0]} for i,x in enumerate(xs)]
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
   self.fixture(root);rows=[json.loads(s) for s in (root/'reverse_history.jsonl').read_text().splitlines()]
   rows[1]['body_vertices_m']=body(99)
   (root/'reverse_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   with self.assertRaisesRegex(ValueError,'completion body differs'):measure.analyze(root)
   self.fixture(root);rows=[json.loads(s) for s in (root/'reverse_history.jsonl').read_text().splitlines()]
   rows[1]['velocity_mps']=[1,0]
   (root/'reverse_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   with self.assertRaisesRegex(ValueError,'velocity contradicts'):measure.analyze(root)
 def test_reverse_gear_without_backward_motion_does_not_count(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   rows=[json.loads(s) for s in (root/'reverse_history.jsonl').read_text().splitlines()]
   rows[1]['ego_forward_xy']=[-1,0]
   rows[2]['ego_forward_xy']=[-1,0]
   rows[1]['heading_deg']=180;rows[2]['heading_deg']=180
   rows[1]['velocity_mps']=[1,0];rows[2]['velocity_mps']=[1,0]
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
 def test_pinned_reverse_completion_reads_same_original_fields(self):
  sys.path.insert(0,str(ROOT.parents[1]/'runtime'/'scenario_pipeline'))
  from worker_exchange.native_output import assess_physical
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   config={'law_id':'NRS-484B-113-2','cell_id':'C215286','rate_hz':20,
           'duration_s':0.15,'motion_route_xy_m':[[10,0]]}
   (root/'config.json').write_text(json.dumps(config))
   (root/'trace.jsonl').write_text('{}\n')
   self.assertTrue(measure.analyze(root)['reverse_body_on_or_over_crosswalk'])
   checked=assess_physical(root,config,[])
   self.assertEqual(checked['physical_checks']['setup']['status'],'met')
   self.assertEqual(checked['physical_checks']['maneuver']['status'],'met')
   rows=[json.loads(s) for s in (root/'reverse_history.jsonl').read_text().splitlines()]
   for row in rows:row.pop('velocity_mps')
   (root/'reverse_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   self.assertEqual(assess_physical(root,config,[])['physical_checks']['maneuver']['status'],'unverified')
 def test_runner_static_and_site_preparation(self):
  config=json.loads((ROOT/'config.json').read_text())
  self.assertEqual(runner.validate_config(config)['rate_hz'],20)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   packet=json.loads((root/'site_packet.json').read_text())
   packet['start_transform']={'x':16,'y':0,'z':0.3,'yaw_deg':0}
   packet['start_body_vertices_xy_m']=body(16)
   packet['target_distances_m']={'over':6,'short':2}
   prepared,start,forward,target=runner.prepare_site(packet,root,config)
   self.assertEqual(target,6)
   self.assertEqual(prepared['targets']['short_distance_m'],2)
   self.assertEqual(forward,[1,0])
   config['selected_case_id']=runner.SHORT
   self.assertEqual(runner.prepare_site(packet,root,config)[-1],2)
   packet['start_transform']['yaw_deg']=180
   with self.assertRaisesRegex(ValueError,'Over target body misses'):
    runner.prepare_site(packet,root,config)
 def test_four_native_camera_spawn_and_cleanup(self):
  from camera_setup import source_cameras,PROFILE
  class Blueprint:
   def __init__(self):self.attributes={}
   def set_attribute(self,key,value):self.attributes[key]=value
  class Sensor:
   def __init__(self):self.stopped=False;self.destroyed=False
   def stop(self):self.stopped=True
   def destroy(self):self.destroyed=True
  sensors=[];blueprint=Blueprint()
  def spawn(bp,transform,**kwargs):
   self.assertIs(bp,blueprint)
   self.assertEqual(transform,'pose')
   sensor=Sensor();sensors.append(sensor);return sensor
  world=NS(get_blueprint_library=lambda:NS(find=lambda name:blueprint),spawn_actor=spawn)
  config=json.loads((ROOT/'config.json').read_text())
  with source_cameras(world,object(),{name:'pose' for name in PROFILE},config['cameras']) as active:
   self.assertEqual(set(active),set(PROFILE))
   self.assertEqual(blueprint.attributes['sensor_tick'],'0.05')
  self.assertEqual(len(sensors),4)
  self.assertTrue(all(s.stopped and s.destroyed for s in sensors))
 def test_saved_finalizer_writes_source_bound_result_and_rejects_missing_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);attempt=root/'attempt';attempt.mkdir();self.fixture(attempt)
   config=json.loads((ROOT/'config.json').read_text())
   config['duration_s']=.15
   config['motion_route_xy_m']=[[10,0]]
   (attempt/'config.json').write_text(json.dumps(config))
   (attempt/'trace.jsonl').write_text('{}\n')
   (attempt/'capture').mkdir();(attempt/'capture'/'evidence.jsonl').write_text('{}\n')
   for name in finalizer.CAMERAS:(attempt/name).write_text('synthetic placeholder; no decode claim')
   report=finalizer.finalize(attempt,root/'analysis-report.json')
   self.assertTrue(report['measurements']['reverse_crosswalk']['value']['reverse_body_on_or_over_crosswalk'])
   result=json.loads((attempt/'result.json').read_text())
   self.assertTrue(result['target_checks'][0]['matched'])
   self.assertEqual(result['physical_checks']['maneuver']['status'],'met')
   self.assertFalse(report['legal_verdict_asserted'])
   self.assertTrue((attempt/'channels'/'crosswalk_overlap.jsonl').is_file())
   fresh=root/'negative';fresh.mkdir();self.fixture(fresh)
   (fresh/'config.json').write_text(json.dumps(config))
   (fresh/'trace.jsonl').write_text('{}\n')
   (fresh/'capture').mkdir();(fresh/'capture'/'evidence.jsonl').write_text('{}\n')
   for name in finalizer.CAMERAS:(fresh/name).write_text('synthetic placeholder')
   (fresh/'site_packet.json').unlink()
   with self.assertRaisesRegex(ValueError,'site_packet.json'):
    finalizer.finalize(fresh,root/'negative-analysis.json')
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
