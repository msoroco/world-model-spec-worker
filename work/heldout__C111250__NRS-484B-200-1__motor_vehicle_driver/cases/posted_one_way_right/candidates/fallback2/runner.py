"""C111250 first exact Native capture. CARLA is imported only for an operator run."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from threading import Condition
from time import monotonic

from road_half import NativeRoadHalfAdapter, construct

CAMERAS={
 'overview':((-8.,0.,8.),(-12.,0.,0.),(1920,1080),95),
 'approach':((1.2,0.,2.),(0.,0.,0.),(1280,720),90),
 'reference_corner':((-3.,2.5,2.6),(-7.,0.,0.),(1280,720),100),
 'driver_reference':((.6,-.35,1.6),(0.,0.,0.),(1280,720),85),
}

def _sha(data):return hashlib.sha256(data).hexdigest()

def check(config):
 cfg=json.loads(Path(config).read_text())
 if cfg['law_id']!='NRS-484B-200-1' or cfg['cell_id']!='C111250' or cfg['actor']!='motor_vehicle_driver':
  raise ValueError('Frozen law/cell/actor identity differs')
 if cfg['selected_case_id']!='heldout__C111250__NRS-484B-200-1__motor_vehicle_driver__posted_one_way_right':
  raise ValueError('First exact case identity differs')
 if cfg['rate_hz']!=20 or cfg['frames']!=160 or cfg['duration_s']!=8:
  raise ValueError('Original 20 Hz capture contract differs')
 if [(c['name'],c['width'],c['height']) for c in cfg['cameras']]!=[(n,*v[2]) for n,v in CAMERAS.items()]:
  raise ValueError('Four named source cameras differ')
 if cfg['case']['exception']!='posted_one_way' or cfg['case']['body_side']!='right':
  raise ValueError('First road-half exception/body-side variable differs')
 return cfg

class SourceCameras:
 def __init__(self,world,carla,ego,output):
  self.world,self.carla,self.ego,self.output=world,carla,ego,Path(output)
  self.condition=Condition();self.encoders={};self.sensors=[]
  self.frames={name:[] for name in CAMERAS};self.errors=[];self.closed=False
  try:
   for name,(place,angles,size,fov) in CAMERAS.items():
    stderr=(self.output/(name+'-encoder.log')).open('wb')
    process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo',
     '-pixel_format','bgra','-video_size',f'{size[0]}x{size[1]}','-framerate','20','-i','pipe:0',
     '-an','-c:v','ffv1','-threads','1',str(self.output/(name+'.mkv'))],
     stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=stderr)
    self.encoders[name]=(process,stderr)
    blueprint=world.get_blueprint_library().find('sensor.camera.rgb')
    for key,value in (('image_size_x',size[0]),('image_size_y',size[1]),('fov',fov),('sensor_tick',.05)):
     blueprint.set_attribute(key,str(value))
    sensor=world.spawn_actor(blueprint,carla.Transform(carla.Location(*place),carla.Rotation(*angles)),attach_to=ego)
    self.sensors.append(sensor)
    sensor.listen(lambda image,camera=name:self._receive(camera,image))
  except BaseException:
   self.close();raise
 def _receive(self,name,image):
  with self.condition:
   try:
    if self.closed:raise ValueError('Original camera arrived after closure')
    size=CAMERAS[name][2]
    if (image.width,image.height)!=size or len(image.raw_data)!=size[0]*size[1]*4:
     raise ValueError('Original camera payload incomplete')
    if self.frames[name] and image.frame<=self.frames[name][-1]['carla_frame']:
     raise ValueError('Original camera frames unordered')
    process=self.encoders[name][0]
    if process.poll() is not None:raise ValueError('Original camera encoder exited early')
    process.stdin.write(bytes(image.raw_data))
    self.frames[name].append({'carla_frame':int(image.frame),'time_s':float(image.timestamp)})
   except BaseException as error:self.errors.append(error)
   finally:self.condition.notify_all()
 def wait(self,frame,timeout_s=15):
  deadline=monotonic()+timeout_s
  with self.condition:
   while True:
    if self.errors:raise ValueError('Original camera callback failed') from self.errors[0]
    if all(any(row['carla_frame']==frame for row in rows) for rows in self.frames.values()):return
    remaining=deadline-monotonic()
    if remaining<=0:raise ValueError('Missing synchronized original camera frame')
    self.condition.wait(remaining)
 def close(self):
  if self.closed:return
  self.closed=True
  for sensor in reversed(self.sensors):
   sensor.stop();sensor.destroy()
  for name,(process,stderr) in self.encoders.items():
   try:
    if process.stdin and not process.stdin.closed:process.stdin.close()
    if process.wait(timeout=60):raise ValueError('Original camera encoder failed: '+name)
   finally:stderr.close()
 def seal(self,frames,times):
  self.close()
  for name,rows in self.frames.items():
   if [row['carla_frame'] for row in rows]!=frames or any(abs(a['time_s']-b)>.05 for a,b in zip(rows,times)):
    raise ValueError('Original camera/body frame join differs: '+name)
   with (self.output/(name+'-frames.jsonl')).open('x') as stream:
    for row in rows:stream.write(json.dumps(row)+'\n')
  return {name:0 for name in CAMERAS}

def _corners(actor):
 points=[]
 for vertex in actor.bounding_box.get_world_vertices(actor.get_transform()):
  point=[float(vertex.x),float(vertex.y)]
  if not any(math.dist(point,other)<1e-4 for other in points):points.append(point)
 if len(points)!=4:raise ValueError('Original Native body footprint incomplete')
 return points

def _control(actor,target,carla):
 transform=actor.get_transform();p=transform.location;v=actor.get_velocity()
 dx=target.x-p.x;dy=target.y-p.y
 desired=math.atan2(dy,dx);current=math.radians(transform.rotation.yaw)
 error=(desired-current+math.pi)%(2*math.pi)-math.pi
 steer=max(-.6,min(.6,error*.8));speed=math.sqrt(v.x*v.x+v.y*v.y)
 throttle=max(0.,min(.55,.25+.18*(4.-speed)))
 if math.hypot(dx,dy)<2:throttle=0.
 actor.apply_control(carla.VehicleControl(throttle=throttle,steer=steer,brake=.25 if throttle==0 else 0.))

def _apply_ego_spawn_offset(site,cfg):
 offset=float(cfg['engineering']['ego_spawn_offset_m'])
 if not 0.5<=offset<=5.:raise ValueError('Fallback ego spawn offset invalid')
 site['spawn_s_m']=dict(site['spawn_s_m'])
 site['spawn_s_m']['ego']=float(site['spawn_s_m']['ego'])+offset
 site['route_s_m']=dict(site['route_s_m'])
 site['route_s_m']['ego']=[float(s)+offset for s in site['route_s_m']['ego']]
 return offset

def run(output,host,port,config):
 cfg=check(config)
 import carla
 from pipeline_capture import PipelineCapture
 from worker_exchange.native_output import FrameMap,seal_capture
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 if any((output/name).exists() for name in ('road_geometry.json','body_history.jsonl','capture-seal.json')):
  raise ValueError('Prior original Native sources must be retained')
 site_path=Path(os.environ['ROAD_HALF_SITE_SOURCE'])
 site_data=site_path.read_bytes();expected=os.environ['ROAD_HALF_SITE_SHA256']
 if _sha(site_data)!=expected:raise ValueError('Native road site source hash differs')
 site=json.loads(site_data)
 _apply_ego_spawn_offset(site,cfg)
 client=carla.Client(host,int(port));client.set_timeout(30.)
 world=client.get_world();old=world.get_settings();adapter=NativeRoadHalfAdapter(world,carla,site)
 cameras=None;pipeline=None;frame_map=None;body_stream=None
 completed=False;restored=False;errors=[];frames=[];times=[]
 try:
  settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
  world.apply_settings(settings)
  scene=construct(adapter,'posted_one_way','right');ego=scene['ego']['actor']
  geometry=dict(scene['road'],centerline=site['centerline'],right_half_sign=site['right_half_sign'],
                survey_source=expected,site_source_sha256=expected)
  road_bytes=(json.dumps(geometry,indent=2)+'\n').encode()
  (output/'road_geometry.json').write_bytes(road_bytes)
  (output/'exception_context.json').write_text(json.dumps({'road_id':site['road_id'],
   'road_sha256':_sha(road_bytes),'exception':'posted_one_way','feature':'surveyed_one_way_sign',
   'sign_source_sha256':_sha(sign_bytes)},indent=2)+'\n')
  sign=dict(scene['features'][0])
  sign['native_readback']={key:value for key,value in sign['native_readback'].items() if key!='actor'}
  sign_bytes=(json.dumps(sign,indent=2)+'\n').encode()
  (output/'one_way_sign_original.json').write_bytes(sign_bytes)
  (output/'actor_identity.json').write_text(json.dumps({'subject_blueprint':scene['ego']['blueprint_id'],
   'subject_actor_id':ego.id},indent=2)+'\n')
  (output/'capture_contract.json').write_text(json.dumps({'cameras':list(CAMERAS),'rate_hz':20,
   'expected_frames':160,'duration_s':8},indent=2)+'\n')
  cameras=SourceCameras(world,carla,ego,output)
  pipeline=PipelineCapture(client,ego,output,cfg['selected_case_id'],required_observations=('rel.occupies',))
  frame_map=FrameMap(output/'video_frames.jsonl');body_stream=(output/'body_history.jsonl').open('x')
  target=adapter._waypoint(scene['ego']['lane_id'],scene['ego']['route_s_m'][-1]).transform.location
  for index in range(cfg['frames']):
   _control(ego,target,carla)
   frame=world.tick();cameras.wait(frame);snapshot=world.get_snapshot()
   if snapshot.frame!=frame:raise ValueError('Original Native snapshot identity differs')
   time_s=float(snapshot.timestamp.elapsed_seconds)
   body_stream.write(json.dumps({'frame':frame,'time_s':time_s,'ground_corners':_corners(ego)},allow_nan=False)+'\n')
   frame_map.append(frame,time_s)
   captured=pipeline.capture(frame,time_s)
   if captured['frame']!=frame or captured['time_s']!=time_s:
    raise ValueError('Original Native pipeline/body frame join differs')
   frames.append(frame);times.append(time_s)
  completed=True
 except BaseException as error:
  errors.append(str(error));raise
 finally:
  if body_stream:body_stream.close()
  if frame_map:frame_map.close()
  if pipeline:pipeline.close(confirmed=completed)
  if cameras:cameras.close()
  adapter.close();world.apply_settings(old)
  current=world.get_settings()
  restored=current.synchronous_mode==old.synchronous_mode and current.fixed_delta_seconds==old.fixed_delta_seconds
  if not restored:raise ValueError('Native world settings restoration differs')
 codes=cameras.seal(frames,times)
 (output/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'native',
  'diagnostic_fixture':False,'original_frames':len(frames)})+'\n')
 seal_capture(output,frames=len(frames),restoration={'restored':restored},errors=errors,encoder_exit_codes=codes)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
 parser.add_argument('--config',default='config.json');parser.add_argument('--output-dir')
 parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000)
 args=parser.parse_args()
 if args.check:check(args.config)
 else:run(args.output_dir,args.host,args.port,args.config)
