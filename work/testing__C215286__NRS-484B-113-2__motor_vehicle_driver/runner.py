"""CARLA-lazy, source-bound reverse-crosswalk capture for C215286.

The site packet and documents are materialized with the exact construction.
This runner attempts motion and retains original sources; it makes no legal or
physical-acceptance claim.
"""
import argparse
import json
import math
from contextlib import ExitStack
from pathlib import Path
from queue import Empty,Queue

from camera_encoder import FFV1Writer
from camera_setup import PROFILE,source_cameras
from reverse_control import reverse_vehicle
from reverse_route import ReverseTargetController,prepare_reviewed_pair

ASSIGNMENT='testing__C215286__NRS-484B-113-2__motor_vehicle_driver'
OVER=ASSIGNMENT+'__reverse_over_crosswalk'
SHORT=ASSIGNMENT+'__reverse_stops_before_crosswalk'
INTERSECTION=ASSIGNMENT+'__reverse_into_intersection'
INTERSECTION_STOP=ASSIGNMENT+'__reverse_stops_before_intersection'
CORNER=ASSIGNMENT+'__reverse_around_street_corner'
CORNER_STOP=ASSIGNMENT+'__reverse_stops_before_street_corner'
CAMERAS=tuple(PROFILE)


def validate_config(config):
 if config.get('law_id')!='NRS-484B-113-2' or config.get('cell_id')!='C215286' or config.get('actor')!='motor_vehicle_driver':
  raise ValueError('Exact C215286 law/cell/actor required')
 if config.get('selected_case_id') not in (OVER,SHORT):raise ValueError('Exact reverse case required')
 supported=set(config.get('supported_case_ids',[]))
 if supported!={OVER,SHORT} and supported!={OVER,SHORT,INTERSECTION,INTERSECTION_STOP,CORNER,CORNER_STOP}:
  raise ValueError('Exact selected reverse case inventory required')
 if config.get('rate_hz')!=20 or config.get('duration_s')!=45:
  raise ValueError('Pinned 20 Hz and 45-second capture required')
 cameras=config.get('cameras')
 if not isinstance(cameras,list) or [r.get('name') for r in cameras]!=list(CAMERAS):
  raise ValueError('Four ordered source cameras required')
 if any((r.get('width'),r.get('height'))!=PROFILE[r['name']] or
        type(r.get('fov_deg')) not in (int,float) or not 30<=r['fov_deg']<=120
        for r in cameras):raise ValueError('Pinned camera size/FOV required')
 if not isinstance(config.get('required_atoms'),list):raise ValueError('Required atom inventory missing')
 if config.get('site_packet')!='site_packet.json':raise ValueError('Exact saved site packet required')
 return config


def prepare_site(packet,source_root,config):
 transform=packet.get('start_transform')
 if not isinstance(transform,dict):raise ValueError('Reviewed Native start transform required')
 for key in ('x','y','z','yaw_deg'):
  value=transform.get(key)
  if type(value) not in (int,float) or not math.isfinite(value):
   raise ValueError('Finite Native start transform required: '+key)
 forward=[math.cos(math.radians(transform['yaw_deg'])),math.sin(math.radians(transform['yaw_deg']))]
 body=packet.get('start_body_vertices_xy_m')
 if not isinstance(body,list) or len(body)<4:raise ValueError('Reviewed starting complete body required')
 distances=packet.get('target_distances_m')
 if not isinstance(distances,dict):raise ValueError('Both reverse target distances required')
 prepared=prepare_reviewed_pair(packet,source_root,body,forward,
                                over_distance_m=distances.get('over'),
                                short_distance_m=distances.get('short'),
                                native_map_id=packet.get('native_map_id'),
                                road_id=packet.get('road_id'),
                                crosswalk_id=packet.get('crosswalk_id'))
 selected=distances['over' if config['selected_case_id']==OVER else 'short']
 return prepared,transform,forward,float(selected)


def _body(actor):
 transform=actor.get_transform()
 vertices=actor.bounding_box.get_world_vertices(transform)
 points=[[float(v.x),float(v.y)] for v in vertices]
 if len(points)<4 or any(not all(math.isfinite(c) for c in p) for p in points):
  raise ValueError('Incomplete original Native complete body')
 return points


def _center(points):
 return [(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in (0,1)]


def _record(actor,snapshot,packet):
 transform=actor.get_transform();velocity=actor.get_velocity()
 yaw=float(transform.rotation.yaw)
 if not math.isfinite(yaw):raise ValueError('Nonfinite Native heading')
 body=_body(actor);forward=[math.cos(math.radians(yaw)),math.sin(math.radians(yaw))]
 values=[float(velocity.x),float(velocity.y)]
 if not all(math.isfinite(v) for v in values):raise ValueError('Nonfinite Native velocity')
 return {'frame':int(snapshot.frame),'time_s':float(snapshot.timestamp.elapsed_seconds),
         'road_id':packet['road_id'],'crosswalk_id':packet['crosswalk_id'],
         'native_reverse':bool(actor.get_control().reverse),
         'ego_forward_xy':forward,'ego_body_vertices_xy_m':body,
         'body_vertices_m':body,'heading_deg':yaw,'velocity_mps':values,
         'actor_id':int(actor.id)}


def _sensor_frame(queue,frame):
 for _ in range(6):
  try:image=queue.get(timeout=10)
  except Empty as error:raise ValueError('Source camera frame missing') from error
  if image.frame==frame:return image
  if image.frame>frame:raise ValueError('Source camera skipped Native frame')
 raise ValueError('Source camera frame join failed')


def _camera_transforms(carla,packet,transform):
 points=packet['crosswalk_polygon_xy_m']
 x=sum(p[0] for p in points)/len(points);y=sum(p[1] for p in points)/len(points)
 z=transform['z'];yaw=transform['yaw_deg']
 def pose(px,py,pz,heading,pitch):
  return carla.Transform(carla.Location(x=px,y=py,z=pz),carla.Rotation(yaw=heading,pitch=pitch))
 return {'overview':pose(x,y,z+35,yaw,-75),
         'approach':pose(transform['x']+10,transform['y'],z+6,yaw+180,-15),
         'reference_corner':pose(x+8,y+8,z+8,yaw-135,-30),
         'driver_reference':pose(1,0,1.65,180,-5)}


def require_native_site_review(packet):
 if (packet.get('site_review_status')!='reviewed_native_site'
     or not packet.get('reviewer') or not packet.get('district_review_basis')
     or not packet.get('crosswalk_review_basis') or not packet.get('camera_review_basis')
     or any('synthetic' in str(packet.get(key,'')).lower() for key in
            ('reviewer','district_review_basis','crosswalk_review_basis','camera_review_basis'))):
  raise ValueError('Original Native district, crosswalk and camera review required before capture')


def capture(args,config):
 output=Path(args.output_dir).resolve()
 if not output.is_dir() or not (output/'construction.json').is_file():
  raise ValueError('Use runtime.py capture to materialize exact construction first')
 from reviewed_site_install import install
 install(output,config.get('selected_case_id',''))
 packet=json.loads((output/'site_packet.json').read_text())
 require_native_site_review(packet)
 prepared,start,forward,target=prepare_site(packet,output,config)
 import carla
 from pipeline_capture import PipelineCapture
 from worker_exchange.native_output import FrameMap,seal_capture
 from worker_exchange.world_restore import snapshot as snapshot_world,restore
 client=carla.Client(args.host,args.port);client.set_timeout(30)
 saved=snapshot_world(client);world=client.get_world();actor=None;capture_helper=None
 encoders={};frames=0;error=None
 try:
  if world.get_map().name!=packet['native_map_id']:
   raise ValueError('Native map differs from reviewed site')
  settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
  world.apply_settings(settings)
  location=carla.Location(x=start['x'],y=start['y'],z=start['z'])
  waypoint=world.get_map().get_waypoint(location,project_to_road=False)
  if waypoint is None or waypoint.road_id!=packet['road_id']:
   raise ValueError('Reviewed Native start is not on selected road')
  blueprint=world.get_blueprint_library().find(packet['vehicle_blueprint_id'])
  actor=world.try_spawn_actor(blueprint,carla.Transform(location,carla.Rotation(yaw=start['yaw_deg'])))
  if actor is None:raise ValueError('Native reverse vehicle spawn failed')
  actual_body=_body(actor)
  # The reviewed body is a planning footprint; the Native body must be checked
  # against both target geometries before any motion is attempted.
  actual=prepare_reviewed_pair(packet,output,actual_body,forward,
                               over_distance_m=packet['target_distances_m']['over'],
                               short_distance_m=packet['target_distances_m']['short'],
                               native_map_id=packet['native_map_id'],road_id=packet['road_id'],
                               crosswalk_id=packet['crosswalk_id'])
  (output/'crosswalk_context.json').write_text(json.dumps({
    'native_map_id':packet['native_map_id'],'road_id':packet['road_id'],
    'crosswalk_id':packet['crosswalk_id'],
    'crosswalk_geometry_source':packet['crosswalk_geometry_source']['path'],
    'crosswalk_camera_source':packet['crosswalk_marking_source']['path'],
    'reverse_route_source':'original Native vehicle body and paired target distances',
    'residence_district_source':packet['district_source']['path'],
    'crosswalk_polygon_xy_m':packet['crosswalk_polygon_xy_m'],
    'site_source_review':prepared['site_review'],
    'native_target_review':actual['targets']},indent=2)+'\n')
  origin=_center(actual_body)
  controller=ReverseTargetController(origin,forward,target)
  transforms=_camera_transforms(carla,packet,start)
  with reverse_vehicle(world,actor,carla.VehicleControl,throttle=.1):
   with source_cameras(world,actor,transforms,config['cameras']) as sensors:
    queues={name:Queue() for name in CAMERAS}
    for name,sensor in sensors.items():sensor.listen(lambda image,name=name:queues[name].put(image))
    with ExitStack() as stack:
     for name,(width,height) in PROFILE.items():
      encoders[name]=stack.enter_context(FFV1Writer(output/(name+'.mkv'),width,height))
     mapping=stack.enter_context(FrameMap(output/'video_frames.jsonl'))
     history=stack.enter_context((output/'reverse_history.jsonl').open('x',buffering=1))
     capture_helper=PipelineCapture(client,actor,output,config['selected_case_id'],
                                    required_observations=config['required_atoms'])
     try:
      for _ in range(config['duration_s']*config['rate_hz']):
       body=_body(actor);velocity=actor.get_velocity()
       speed=math.hypot(float(velocity.x),float(velocity.y))
       command=controller.step(_center(body),speed)
       actor.apply_control(carla.VehicleControl(throttle=command['throttle'],
                                                brake=command['brake'],reverse=True))
       world.tick();snapshot=world.get_snapshot()
       for name in CAMERAS:encoders[name].write(bytes(_sensor_frame(queues[name],snapshot.frame).raw_data))
       capture_helper.capture(snapshot.frame,snapshot.timestamp.elapsed_seconds)
       mapping.append(snapshot.frame,snapshot.timestamp.elapsed_seconds)
       history.write(json.dumps(_record(actor,snapshot,packet),separators=(',',':'))+'\n')
       frames+=1
     finally:
      capture_helper.close();capture_helper=None
 except BaseException as caught:
  error=caught;raise
 finally:
  cleanup=[]
  if capture_helper is not None:
   try:capture_helper.close(confirmed=False)
   except BaseException as caught:cleanup.append(str(caught))
  if actor is not None:
   try:actor.destroy()
   except BaseException as caught:cleanup.append(str(caught))
  restoration=restore(client,saved)
  if error is None and not cleanup:
   seal_capture(output,frames=frames,restoration=restoration,errors=[],
                encoder_exit_codes={name:e.exit_code for name,e in encoders.items()},
                context={'crosswalk_site_source_check':prepared['site_review'],
                         'physical_acceptance_claimed':False})
  if error is None and cleanup:raise ValueError('Native cleanup failed: '+'; '.join(cleanup))


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
 parser.add_argument('--output-dir');parser.add_argument('--host',default='127.0.0.1')
 parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
 config=validate_config(json.loads(Path(__file__).with_name('config.json').read_text()))
 if args.check:
  print(json.dumps({'case_id':config['selected_case_id'],'cpu_check_passed':True,'carla_started':False}))
  return
 if not args.output_dir:raise ValueError('--output-dir required for Native capture')
 capture(args,config)


if __name__=='__main__':main()
