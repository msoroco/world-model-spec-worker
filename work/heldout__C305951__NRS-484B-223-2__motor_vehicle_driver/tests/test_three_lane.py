from __future__ import annotations
import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('three_lane',Path(__file__).resolve().parents[1]/'three_lane.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Fake:
 def __init__(self):self.calls=[]
 def road(self,**x):self.calls.append(('road',x));return x
 def lane_marking(self,**x):self.calls.append(('lane_marking',x));return x
 def vehicle(self,**x):self.calls.append(('vehicle',x));return x
 def occluder(self,**x):self.calls.append(('occluder',x));return x
 def turn_route(self,**x):self.calls.append(('turn_route',x));return x
 def lane_allocation(self,**x):self.calls.append(('lane_allocation',x));return x
 def sign(self,**x):self.calls.append(('sign',x));return x
class ThreeLaneTests(unittest.TestCase):
 def test_all_variants_create_marked_lanes_and_needed_features(self):
  for name in m.CASES:
   f=Fake();scene=m.construct(f,name)
   self.assertEqual(len(scene['lane_markings']),4)
   self.assertEqual(scene['ego']['lane'],m.CASES[name][0])
   if name=='center_pass_occluded':self.assertIn('occluder',[x[0] for x in f.calls])
   if name=='center_allocated_signed':self.assertIn('sign',[x[0] for x in f.calls])
   if name=='center_prepare_left':self.assertIn('turn_route',[x[0] for x in f.calls])
 def sample(self):
  c={'marked_lane_count':3,'marking_source':'original-markings','allocation_source':'original-allocation',
     'exception_variant':'passing_clear','passing_source':'original-passing','sight_source':'original-sight'}
  frames=[{'frame':i,'lane':'center','body_source':'original-body'} for i in range(3)]
  return c,frames
 def test_original_lane_occupancy_and_missing_sight(self):
  c,f=self.sample();r=m.measure(c,f);self.assertTrue(r['center_occupied'])
  self.assertFalse(r['extreme_left_occupied']);self.assertIsNone(r['legal_lane_judgment'])
  c['sight_source']=''
  with self.assertRaisesRegex(ValueError,'sight source'):m.measure(c,f)
 def test_audit_rejects_changed_fixed_condition(self):
  c,f=self.sample();a=m.measure(c,f);a.update(road_hash='r',marking_hash='m',camera_plan_hash='cam',duration_s=8,actor_hash='a')
  b=dict(a,exception_variant='passing_occluded')
  self.assertTrue(m.audit_comparison(a,b,'passing_visibility')['comparison_complete'])
  with self.assertRaisesRegex(ValueError,'fixed condition'):m.audit_comparison(a,dict(b,marking_hash='x'),'passing_visibility')
if __name__=='__main__':unittest.main()
