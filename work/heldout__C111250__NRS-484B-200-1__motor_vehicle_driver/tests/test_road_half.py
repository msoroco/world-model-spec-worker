from __future__ import annotations
import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('road_half',Path(__file__).resolve().parents[1]/'road_half.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Fake:
 def __init__(self):self.calls=[]
 def road(self,**x):self.calls.append(('road',x));return x
 def vehicle(self,**x):self.calls.append(('vehicle',x));return x
 def closure(self,**x):self.calls.append(('closure',x));return x
 def sign(self,**x):self.calls.append(('sign',x));return x
class RoadHalfTests(unittest.TestCase):
 def test_all_exception_variants_create_physical_features(self):
  for exception in m.EXCEPTIONS:
   f=Fake();scene=m.construct(f,exception,'left')
   self.assertEqual(scene['ego']['route'][0][1],1)
   self.assertEqual(scene['road']['lanes'],3 if exception=='three_lanes' else (1 if exception=='posted_one_way' else 2))
   if exception=='right_half_closed':self.assertIn('closure',[x[0] for x in f.calls])
   if exception=='posted_one_way':self.assertIn('sign',[x[0] for x in f.calls])
   if exception=='overtaking_same_direction':self.assertEqual(len([x for x in f.calls if x[0]=='vehicle']),2)
 def sample(self):
  c={'exception':'none','exception_source':'original-road-context','road_source':'original-map','centerline':[[0,0],[10,0]]}
  f=[{'frame':i,'body_source':'original-footprint','ground_corners':[[i,-1],[i+1,-1],[i+1,-2],[i,-2]]} for i in range(2)]
  return c,f
 def test_original_full_body_side_and_missing_source(self):
  c,f=self.sample();r=m.measure(c,f);self.assertFalse(r['any_left_half_body'])
  f[0]['ground_corners']=[[0,1],[1,1],[1,2],[0,2]]
  self.assertTrue(m.measure(c,f)['any_left_half_body'])
  c['exception_source']=''
  with self.assertRaisesRegex(ValueError,'sourced'):m.measure(c,f)
 def test_fixed_condition_comparison(self):
  c,f=self.sample();a=m.measure(c,f);a.update(road_hash='r',centerline_hash='c',camera_plan_hash='cam',duration_s=8,actor_hash='a')
  b=dict(a,any_left_half_body=True)
  self.assertTrue(m.audit_comparison(a,b,'body_side')['comparison_complete'])
  with self.assertRaisesRegex(ValueError,'fixed condition'):m.audit_comparison(a,dict(b,road_hash='x'),'body_side')
if __name__=='__main__':unittest.main()
