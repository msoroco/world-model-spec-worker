from __future__ import annotations
import importlib.util,sys,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('flash_heavy',Path(__file__).resolve().parents[1]/'flashing_yellow_heavy.py')
m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
class Fake:
 def __init__(self):self.calls=[]
 def intersection(self,**x):self.calls.append(('intersection',x));return x
 def signal_head(self,**x):self.calls.append(('signal_head',x));return x
 def official_control_device(self,**x):self.calls.append(('official_device',x));return x
 def vehicle(self,**x):self.calls.append(('vehicle',x));return x
class FlashHeavyTests(unittest.TestCase):
 def test_both_directions_construct_heavy_subject_and_real_signal_requests(self):
  for c in m.CASES.values():
   f=Fake();scene=m.construct(f,c)
   self.assertEqual([x[0] for x in f.calls[:3]],['intersection','signal_head','official_device'])
   self.assertEqual(scene['ego']['vehicle_class'],'heavy_vehicle')
   self.assertEqual(scene['ego']['route'][0][0],-70 if c.direction=='east' else 70)
   self.assertEqual(scene['crossing'] is not None,c.crossing_vehicle)
 def samples(self):
  return [{'time_s':i*.05,'signal_head_visible':True,'yellow_lens_on':m.lamp_on(i*.05),
           'official_device_source':'original-device','signal_source':'original-signal','ego_source':'original-ego',
           'ego_vehicle_class':'heavy_vehicle','approach_direction':'east','ego_speed_mps':3,
           'ego_center_xy':[20-i,0],'crossing_source':'original-crossing'} for i in range(10)]
 def test_original_measurement_and_missing_source_rejected(self):
  self.assertIsNone(m.measure(self.samples())['legal_caution_judgment'])
  bad=self.samples();bad[2]['ego_source']=''
  with self.assertRaisesRegex(ValueError,'source missing'):m.measure(bad)
  bad=self.samples();bad[3]['ego_vehicle_class']='motor_vehicle'
  with self.assertRaisesRegex(ValueError,'heavy subject'):m.measure(bad)
 def test_intermittent_light_and_fixed_comparison(self):
  bad=self.samples()
  for r in bad:r['yellow_lens_on']=True
  with self.assertRaisesRegex(ValueError,'intermittent'):m.measure(bad)
  a=dict(samples=[1],map_hash='m',signal_head_hash='s',official_device_source='d',blink_period_s=.5,
         camera_plan_hash='c',duration_s=8,vehicle_class='heavy_vehicle',target_mps=3,crossing_vehicle=True,direction='east')
  b=dict(a,target_mps=7)
  self.assertTrue(m.audit_comparison(a,b,'approach_speed')['comparison_complete'])
  with self.assertRaisesRegex(ValueError,'fixed condition'):m.audit_comparison(a,dict(b,map_hash='x'),'approach_speed')
if __name__=='__main__':unittest.main()
