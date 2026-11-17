from __future__ import annotations
import importlib.util,sys,unittest
from types import SimpleNamespace as Box
from tempfile import TemporaryDirectory
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
    actor=Box(id=100+len(self.spawned),type_id=blueprint.id,transform=transform,
              destroyed=False,get_transform=lambda:transform,
              get_velocity=lambda:Box(x=3.0,y=0.0,z=0.0))
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
  selected_case=m.CASES['west_cautious_proxy']
  camera_waits=[]
  cameras=Box(sensors={name:object() for name in m.SOURCE_CAMERAS},
              wait_for_frame=lambda frame:camera_waits.append(frame))
  collector=m.NativeSampleCollector(scene,selected_case,'source-identified-official-control',cameras)
  rows=[];maps=[]
  with m.NativeYellowController(scene['selected']['light'],Box(Yellow='Yellow',Off='Off')) as control:
   for index in range(10):
    commanded=control.set_at(index*.05)
    row,mapping=collector.capture(Box(frame=500+index,
        timestamp=Box(elapsed_seconds=10+index*.05)),commanded)
    rows.append(row);maps.append(mapping)
  self.assertEqual([m['video_frame'] for m in maps],list(range(10)))
  self.assertEqual([m['carla_frame'] for m in maps],list(range(500,510)))
  self.assertEqual(camera_waits,list(range(500,510)))
  self.assertEqual(rows[0]['official_device_status'],'premise_unverified')
  self.assertIsNone(rows[0]['signal_head_visible'])
  with self.assertRaisesRegex(ValueError,'missing physical yellow signal'):
   m.measure(rows)
  with self.assertRaisesRegex(ValueError,'not contiguous'):
   collector.capture(Box(frame=511,timestamp=Box(elapsed_seconds=10.55)),
                     {'light_actor_id':11,'native_light_state':'Red','yellow_lens_on':False})
  failed=World();failed.fail_crossing=True
  with self.assertRaisesRegex(ValueError,'crossing Native actor spawn failed'):
   m.construct_native(failed,m.CASES['east_cautious_proxy'],'source-identified-official-control',
                      'vehicle.carlamotors.firetruck','vehicle.tesla.model3')
  self.assertTrue(failed.spawned[0].destroyed)
 def test_four_source_cameras_require_joined_original_frames(self):
  class Sensor:
   def __init__(self):self.callback=None;self.stopped=False;self.destroyed=False
   def listen(self,callback):self.callback=callback
   def emit(self,frame,name):
    width,height=m.SOURCE_CAMERAS[name][2]
    self.callback(Box(frame=frame,width=width,height=height,raw_data=b'pixel'))
   def stop(self):self.stopped=True
   def destroy(self):self.destroyed=True
  class Blueprint:
   def __init__(self):self.attributes={}
   def set_attribute(self,key,value):self.attributes[key]=value
  class World:
   def __init__(self):self.sensors=[];self.blueprints=[]
   def get_blueprint_library(self):
    def find(name):
     self.blueprints.append(Blueprint());return self.blueprints[-1]
    return Box(find=find)
   def spawn_actor(self,blueprint,transform,attach_to):
    sensor=Sensor();self.sensors.append(sensor);return sensor
  class Sink:
   def __init__(self):self.frames=[]
   def write(self,image):self.frames.append(image.frame)
  world=World();sinks={name:Sink() for name in m.SOURCE_CAMERAS}
  carla=Box(Location=lambda *args:args,Rotation=lambda *args:args,
            Transform=lambda location,rotation:(location,rotation))
  cameras=m.NativeSourceCameras(world,carla,Box(id=42),sinks)
  self.assertEqual(set(cameras.sensors),{'overview','approach','reference_corner','driver_reference'})
  self.assertTrue(all(bp.attributes['sensor_tick']=='0.05' for bp in world.blueprints))
  for frame in (100,101):
   for name,sensor in cameras.sensors.items():sensor.emit(frame,name)
   cameras.wait_for_frame(frame,timeout_s=.01)
  self.assertEqual(cameras.verify_frames([100,101]),{name:2 for name in m.SOURCE_CAMERAS})
  self.assertTrue(all(sink.frames==[100,101] for sink in sinks.values()))
  with self.assertRaisesRegex(ValueError,'duplicate original'):
   cameras.sensors['overview'].emit(101,'overview')
  with self.assertRaisesRegex(ValueError,'callback failed'):
   cameras.wait_for_frame(102,timeout_s=.01)
  cameras.close()
  self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))
  with self.assertRaisesRegex(ValueError,'exactly four'):
   m.NativeSourceCameras(World(),carla,Box(id=42),{'overview':Sink()})
 def test_lossless_source_sink_checks_raw_bytes_and_encoder_exit(self):
  class Pipe:
   def __init__(self):self.bytes=0;self.closed=False
   def write(self,value):self.bytes+=len(value)
   def close(self):self.closed=True
  class Process:
   def __init__(self):self.stdin=Pipe()
   def wait(self):return 0
  launched=[]
  def popen(command,stdin):
   launched.append((command,stdin));return Process()
  with TemporaryDirectory() as root:
   sink=m.FFV1SourceSink(root,'overview',popen=popen)
   self.assertIn('ffv1',launched[0][0])
   self.assertIn('1920x1080',launched[0][0])
   with self.assertRaisesRegex(ValueError,'raw byte count'):
    sink.write(Box(raw_data=b'short'))
   sink.write(Box(raw_data=bytes(sink.expected_bytes)))
   self.assertEqual(sink.process.stdin.bytes,1920*1080*4)
   sink.close();self.assertTrue(sink.process.stdin.closed)
   with self.assertRaisesRegex(ValueError,'sink closed'):
    sink.write(Box(raw_data=b''))
if __name__=='__main__':unittest.main()
