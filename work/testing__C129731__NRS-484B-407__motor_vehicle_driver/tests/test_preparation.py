import json,pathlib,unittest,importlib.util,math,xml.etree.ElementTree as ET,tempfile
R=pathlib.Path(__file__).resolve().parents[1]
def module(name):
 s=importlib.util.spec_from_file_location(name,R/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Preparation(unittest.TestCase):
 def test_speed_controller_brakes_overshoot(self):
  m=module('runner');c,i=m.command((0,0),0,12,[[0,0,0],[20,0,0]],0,5);self.assertGreater(c['brake'],0);self.assertEqual(c['throttle'],0)
 def test_reverse_controller(self):
  m=module('runner');c,i=m.command((0,0),0,0,[[0,0,0],[-20,0,0]],0,2,True);self.assertTrue(c['reverse']);self.assertAlmostEqual(c['steer'],0)
 def test_turn_controller_direction(self):
  m=module('runner');c,i=m.command((0,0),0,1,[[0,0,0],[10,10,0]],0,4);self.assertGreater(c['steer'],0)
 def test_summary_uses_saved_window(self):
  m=module('finalize');self.assertEqual(m.summarize([{'time_s':0,'value':100},{'time_s':1,'value':2},{'time_s':2,'value':4}],[1,2],'mean'),3)
 def test_summary_missing_fails(self):
  with self.assertRaises(ValueError):module('finalize').summarize([{'time_s':1,'value':None}],[0,2],'mean')
 def test_preserved_evidence(self):
  c=json.loads((R/'config.json').read_text());p=json.loads((R/'case-plan.json').read_text());self.assertEqual(c['actor'],p['actor']);self.assertTrue(p['sources']);self.assertFalse(c['simulate_baseline_by_default']);self.assertEqual(len(c['cameras']),4)
 def test_map_geometry(self):
  x=ET.parse(R/'road.xodr').getroot();self.assertTrue(x.findall('road'));self.assertTrue(all(float(r.attrib['length'])>0 for r in x.findall('road')))
 def test_contact_geometry_preserved(self):
  m=module('geometry');a=m.rectangle((0,0),0,2,1);b=m.rectangle((4,0),0,2,1);self.assertTrue(m.overlaps(a,b));self.assertFalse(m.overlaps(a,m.rectangle((4.01,0),0,2,1)))
 def test_reverse_footprint_crossing(self):
  m=module('geometry');cross=[[148,0],[152,0],[152,3.5],[148,3.5]];self.assertTrue(m.overlaps(m.rectangle((151,1.75),0,2,1),cross));self.assertFalse(m.overlaps(m.rectangle((160,0),0,2,1),cross))
 def test_authored_route_geometry(self):
  c=json.loads((R/'config.json').read_text());self.assertTrue(module('geometry').validate_map(R/'road.xodr',c['mechanism'])['authored_geometry_validated'])
 def test_cleanup_survives_capture_error(self):
  m=module('runner');events=[]
  class BadCapture:
   def close(self,confirmed=False):events.append('capture');raise RuntimeError('capture finalization failed')
  class Actor:
   def stop(self):events.append('sensor_stop')
   def destroy(self):events.append('actor_destroy')
  class World:
   def apply_settings(self,value):events.append('settings')
  class Stream:
   def close(self):events.append('stream')
  with tempfile.TemporaryDirectory(dir=R) as tmp:
   out=pathlib.Path(tmp);result={'maneuver_completed':False,'physical_failure_flags':[]};errors=m.cleanup_resources(BadCapture(),{'a':Stream()},[Actor()],[Actor()],World(),object(),{},result,out,Stream());self.assertEqual(len(errors),1);self.assertTrue((out/'result.json').exists());self.assertEqual(events,['capture','stream','stream','sensor_stop','actor_destroy','settings']);self.assertIn('cleanup_failure',result['physical_failure_flags'])
 def test_required_intersection_branch(self):
  c=json.loads((R/'config.json').read_text())
  if c['mechanism']!='reverse':return
  x=ET.parse(R/'road.xodr').getroot();self.assertIsNotNone(x.find('junction'));cases=c['cases'];by={v['case_id'].rsplit('__',1)[1]:v for v in cases};self.assertIn('outside_intersection_reverse',by);self.assertIn('into_intersection_reverse',by);inside=by['into_intersection_reverse']['variable_assignments'];self.assertIsNotNone(inside['intersection_polygon']['value']);self.assertFalse(inside['street_corner_maneuver']['value']);self.assertEqual(inside['route_start_s']['value'],550)
 def test_comparison_implementation_frozen(self):
  original=(R/'runner.py').read_text()
  for f in (R/'constructions').glob('*.json'):
   d=json.loads(f.read_text());self.assertEqual(next(x['content'] for x in d['files'] if x['path']=='runner.py'),original)

class ProjectionSource(unittest.TestCase):
 def test_no_null_placeholder_channels(self):
  text=(R/'measurements.py').read_text();self.assertNotIn('missing_capability',text);self.assertIn('actor_visibility',text);self.assertIn('visible_relation',text)
 def test_actual_native_feature_authoring(self):
  config=json.loads((R/'config.json').read_text());root=ET.parse(R/'road.xodr').getroot()
  if config['mechanism']=='yield':self.assertEqual(root.find('.//signal').attrib['type'],'205')
  if config['mechanism']=='reverse':self.assertEqual(root.find('.//object').attrib['type'],'crosswalk')
 def test_possible_success_and_measured_checks(self):
  source=(R/'runner.py').read_text();self.assertIn('return 0 if success else 2',source);self.assertIn('validate_output(out,result',source);self.assertIn('measured_target(',source);self.assertIn('recording.tick(frame,time_s,measure)',source)

class FinalCorrections(unittest.TestCase):
 def test_participant_join_order(self):
  m=module('measurements')
  class P:
   def __init__(self,ident):self.id=ident
  self.assertEqual([r['actor_id'] for r in m.ordered_states([P(8),P(4)],[{'actor_id':4},{'actor_id':8}])],[8,4])
  with self.assertRaises(ValueError):m.ordered_states([P(9)],[{'actor_id':4}])
 def test_whole_uturn_footprint(self):
  m=module('geometry');proof=m.validate_uturn_footprint(430);self.assertEqual(proof['sampled_whole_semicircle_poses'],721)
  with self.assertRaises(ValueError):m.validate_uturn_footprint(430,10,8)
 def test_visibility_requires_all_routes_and_nine_body_rays(self):
  m=module('measurements');value={'required_lane_ids':[-1,1],'approaches':[{'lane_id':i,'body_rays_at_probe':[{'clear':True}]*9,'any_body_sight_horizon':{'bound':'at_least','distance_m':230}} for i in [-1,1]]};self.assertTrue(m.validate_visibility(value,[-1,1]));value['approaches'][0]['any_body_sight_horizon']={'bound':'route_limit','unknown':True,'distance_m':220}
  with self.assertRaises(ValueError):m.validate_visibility(value,[-1,1])
 def test_full_scalar_summary_contract_declared(self):
  c=json.loads((R/'config.json').read_text());self.assertEqual(c['measurement_definitions']['sight_distance.minimum_from_either_approach']['statistic'],'min');self.assertEqual(c['measurement_definitions']['backing_intersection_overlap']['statistic'],'max')

class YieldReferenceServo(unittest.TestCase):
 def test_stop_front_reference_and_completed_hold(self):
  m=module('runner');target,hold=m.yield_reference_target(487.1,0,2.4,8,7.99,.05,4);self.assertEqual(target,0);self.assertEqual(hold,8);target,hold=m.yield_reference_target(487.1,0,2.4,8,8,.05,4);self.assertEqual(target,4);self.assertEqual(hold,8)
 def test_nonselected_halt_never_stops(self):
  m=module('runner');target,hold=m.yield_reference_target(488,4,2.4,0,0,.05,4);self.assertEqual(target,4);self.assertEqual(hold,0)
