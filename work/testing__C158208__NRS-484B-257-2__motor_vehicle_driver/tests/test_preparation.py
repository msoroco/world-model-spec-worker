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
  m=module('geometry');cross=[[148,-3.5],[152,-3.5],[152,3.5],[148,3.5]];self.assertTrue(m.overlaps(m.rectangle((151,0),0,2,1),cross));self.assertFalse(m.overlaps(m.rectangle((160,0),0,2,1),cross))
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
