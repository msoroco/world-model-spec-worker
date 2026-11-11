from __future__ import annotations
import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('backing',Path(__file__).resolve().parents[1]/'backing.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Fake:
 def __init__(self):self.calls=[]
 def road(self,**x):self.calls.append(('road',x));return x
 def vehicle(self,**x):self.calls.append(('vehicle',x));return x
class BackingTests(unittest.TestCase):
 def test_construct_creates_narrow_road_and_opposing_traffic(self):
  f=Fake();scene=m.construct(f,other_traffic_mps=3,ego_reverse_mps=1)
  self.assertEqual([x[0] for x in f.calls],['road','vehicle','vehicle'])
  self.assertEqual(scene['ego']['gear'],'reverse')
  self.assertEqual(scene['other']['role'],'other_traffic')
 def samples(self):
  return [{'frame':i,'time_s':i*.05,'ego_source':'original-ego','other_source':'original-other',
           'road_source':'original-road','ego_reverse_gear':True,'ego_xy':[20-i,0],
           'other_xy':[10+i,0],'ego_speed_mps':1,'other_speed_mps':3} for i in range(4)]
 def test_original_displacement_and_sources(self):
  r=m.measure(self.samples());self.assertEqual(r['reverse_displacement_m'],3)
  self.assertIsNone(r['legal_safety_judgment'])
  bad=self.samples();bad[0]['other_source']=''
  with self.assertRaisesRegex(ValueError,'source missing'):m.measure(bad)
  bad=self.samples();bad[-1]['ego_xy']=[25,0]
  with self.assertRaisesRegex(ValueError,'reverse displacement'):m.measure(bad)
 def test_comparison_rejects_changed_fixed_condition(self):
  r=m.measure(self.samples());a=dict(r,map_hash='m',road_hash='r',camera_plan_hash='c',duration_s=8,
     ego_reverse_mps=1,other_actor_hash='o')
  b=dict(a,min_center_distance_m=a['min_center_distance_m']+2)
  self.assertTrue(m.audit_comparison(a,b,'traffic_clearance')['comparison_complete'])
  with self.assertRaisesRegex(ValueError,'fixed condition'):m.audit_comparison(a,dict(b,road_hash='x'),'traffic_clearance')
if __name__=='__main__':unittest.main()
