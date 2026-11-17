from __future__ import annotations
import importlib.util,sys,unittest
from types import SimpleNamespace as Box
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
 def test_native_governed_routes_heavy_spawn_crossing_and_signal_readback(self):
  class Waypoint:
   def __init__(self,x,y,yaw,road=1):
    self.transform=Box(location=Box(x=x,y=y),rotation=Box(yaw=yaw))
    self.road_id=road;self.lane_id=1
   def get_junction(self):return Box(id=7)
   def previous(self,d):return self.shift(-d)
   def next(self,d):return self.shift(d)
   def shift(self,d):
    yaw=self.transform.rotation.yaw
    x=self.transform.location.x+(d if yaw==0 else -d if yaw==180 else 0)
    y=self.transform.location.y+(d if yaw==90 else 0)
    return [Waypoint(x,y,yaw,self.road_id)]
  class Light:
   def __init__(self,actor_id,waypoint):self.id=actor_id;self.waypoint=waypoint;self.state='Red'
   def get_opendrive_id(self):return str(self.id)
   def get_affected_lane_waypoints(self):return [self.waypoint]
   def get_state(self):return self.state
   def set_state(self,value):self.state=value
  class World:
   def __init__(self):
    self.lights=[Light(10,Waypoint(-10,0,0)),Light(11,Waypoint(10,0,180))]
    self.spawned=[];self.fail_crossing=False
   def get_actors(self):return Box(filter=lambda pattern:self.lights)
   def get_map(self):return Box(generate_waypoints=lambda step:[Waypoint(0,0,90,2)])
   def get_blueprint_library(self):return Box(find=lambda name:Box(id=name))
   def try_spawn_actor(self,blueprint,transform):
    if self.fail_crossing and len(self.spawned)==1:return None
    actor=Box(type_id=blueprint.id,transform=transform,destroyed=False)
    actor.destroy=lambda: setattr(actor,'destroyed',True)
    self.spawned.append(actor);return actor
  world=World()
  with self.assertRaisesRegex(ValueError,'official-control source'):
   m.discover_native_control(world,'')
  for case in m.CASES.values():
   scene=m.construct_native(world,case,'source-identified-official-control',
                            'vehicle.carlamotors.firetruck','vehicle.tesla.model3')
   self.assertEqual(scene['selected']['direction'],case.direction)
   self.assertEqual(scene['ego'].type_id,'vehicle.carlamotors.firetruck')
   self.assertEqual(scene['crossing'] is not None,case.crossing_vehicle)
  with m.NativeYellowController(world.lights[0],Box(Yellow='Yellow',Off='Off')) as control:
   self.assertTrue(control.set_at(0)['yellow_lens_on'])
   self.assertFalse(control.set_at(.3)['yellow_lens_on'])
  self.assertEqual(world.lights[0].get_state(),'Red')
  failed=World();failed.fail_crossing=True
  with self.assertRaisesRegex(ValueError,'crossing Native actor spawn failed'):
   m.construct_native(failed,m.CASES['east_cautious_proxy'],'source-identified-official-control',
                      'vehicle.carlamotors.firetruck','vehicle.tesla.model3')
  self.assertTrue(failed.spawned[0].destroyed)
if __name__=='__main__':unittest.main()
