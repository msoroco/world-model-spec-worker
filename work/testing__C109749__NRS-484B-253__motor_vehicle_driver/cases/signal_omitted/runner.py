"""Original opposing-vehicle yielding and left-turn episode."""
import argparse, hashlib, json, math, queue, subprocess, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot,restore
ROOT=Path(__file__).resolve().parent

def check():
 cfg=json.loads((ROOT/'config.json').read_text());tree=ET.parse(ROOT/'scene.xodr');root=tree.getroot()
 roads={r.get('id'):r for r in root.findall('road')};assert {'1','2','3','4','13'}<=set(roads)
 arc=roads['13'].find('planView/geometry/arc');assert arc is not None and abs(float(arc.get('curvature'))-1/7)<1e-6
 links=roads['13'].find('link');assert links.find('predecessor').get('elementId')=='1' and links.find('successor').get('elementId')=='4'
 junction=root.find('junction');assert any(c.get('incomingRoad')=='1' and c.get('connectingRoad')=='13' and c.find('laneLink').get('from')=='-1' for c in junction.findall('connection'))
 assert not any(r.find('signals') is not None for r in root.findall('road'))
 assert cfg['duration_s']==45 and cfg['rate_hz']==20
 assert [(c['name'],c['width'],c['height']) for c in cfg['cameras']]==[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]
 return {'passed':True,'left_turn_connected':True,'two_way_approaches':True,'physical_motion_verified':False}

def route_points(mapping):
 route=[]
 for road,stations in [(1,range(360,393,2)),(13,[i*10.995574287564276/20 for i in range(20)]),(4,range(2,102,2))]:
  for station in stations:
   wp=mapping.get_waypoint_xodr(road,-1,float(station))
   if wp is None:raise ValueError('Native selected lane connection missing')
   loc=wp.transform.location;route.append((loc.x,loc.y))
 return route

def command(actor,route,requested_mps):
 pose=actor.get_transform();x,y=pose.location.x,pose.location.y
 nearest=min(range(len(route)),key=lambda i:(route[i][0]-x)**2+(route[i][1]-y)**2)
 look=route[min(len(route)-1,nearest+4)];angle=math.atan2(look[1]-y,look[0]-x)
 error=(angle-math.radians(pose.rotation.yaw)+math.pi)%(2*math.pi)-math.pi
 speed=actor.get_velocity().length();remaining=math.hypot(route[-1][0]-x,route[-1][1]-y)
 target=min(requested_mps,math.sqrt(max(0,2*1.5*(remaining-2))))
 effort=target-speed
 return {'control':{'throttle':max(0,min(.55,.22*effort)),'brake':max(0,min(.8,-.20*effort)),'steer':max(-.7,min(.7,1.4*error))},'nearest_route_index':nearest,'requested_mps':target}

def run(args):
 import carla
 from pipeline_capture import PipelineCapture
 from analyze import finalize
 client=carla.Client(args.host,args.port);client.set_timeout(60);saved=snapshot(client)
 out=Path(args.output_dir);cfg=json.loads((ROOT/'config.json').read_text());owned=[];encoders={};streams={};queues={};capture=None;errors=[];frames=0
 try:
  world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text());settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
  world.set_weather(carla.WeatherParameters.ClearNoon);mapping=world.get_map();route=route_points(mapping)
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','left_turn_subject')
  wp=mapping.get_waypoint_xodr(13,-1,1);ego=world.spawn_actor(bp,wp.transform);owned.append(ego)
  ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  opposing_bp=world.get_blueprint_library().find('vehicle.tesla.model3');opposing_bp.set_attribute('role_name','opposing_through_vehicle')
  opposing_wp=mapping.get_waypoint_xodr(11,1,7) if cfg.get("opposing_initial")=="inside" else mapping.get_waypoint_xodr(2,1,30);opposing=world.spawn_actor(opposing_bp,opposing_wp.transform);owned.append(opposing)
  opposing.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  follower=world.spawn_actor(opposing_bp,mapping.get_waypoint_xodr(2,1,110).transform);owned.append(follower)
  follower.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  ego.set_light_state(carla.VehicleLightState.LeftBlinker if cfg.get("signal_given",True) else carla.VehicleLightState.NONE)
  for _ in range(20):world.tick()
  geometry={'source':'Native OpenDRIVE map; source-authored route plus actual waypoint readback','approach_road_id':1,'departure_road_id':4,
   'connector_road_id':13,'approach_direction_xy':[1,0],'approach_centerline_point_xy':[-7,0],
   'departure_direction_xy':[0,-1],'departure_centerline_point_xy':[0,-7],
   'intersection_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'two_way':True,'public_highway_designation':'synthetic authored assumption; factual status unverified',
   'route_waypoints_native_xy':route}
  (out/'road_geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
  for spec in cfg['cameras']:
   name,w,h=spec['name'],spec['width'],spec['height'];camera_bp=world.get_blueprint_library().find('sensor.camera.rgb')
   for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:camera_bp.set_attribute(key,str(value))
   if name=='overview':pose=carla.Transform(carla.Location(x=0,y=0,z=60),carla.Rotation(pitch=-90));attached=ego
   elif name=='approach':pose=carla.Transform(carla.Location(x=-8,y=0,z=5),carla.Rotation(pitch=-15));attached=ego
   elif name=='reference_corner':pose=carla.Transform(carla.Location(x=-18,y=18,z=28),carla.Rotation(pitch=-55));attached=None
   else:pose=carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation());attached=ego
   camera=world.spawn_actor(camera_bp,pose,attach_to=attached);owned.append(camera);queues[name]=queue.Queue();camera.listen(queues[name].put)
   streams[name]=(out/(name+'.encoder.log')).open('x');encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra','-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=streams[name])
  capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
  started=world.get_snapshot().timestamp.elapsed_seconds
  with FrameMap(out/'video_frames.jsonl') as fmap,(out/'body_history.jsonl').open('x') as body,(out/'interaction_history.jsonl').open('x') as interactions:
   for i in range(cfg['duration_s']*cfg['rate_hz']):
    opposing_speed=opposing.get_velocity().length();opposing.apply_control(carla.VehicleControl(throttle=max(0,min(.45,.22*(5-opposing_speed))),brake=max(0,min(.5,.2*(opposing_speed-5)))))
    opponent_vertices=[[v.x,v.y,v.z] for v in opposing.bounding_box.get_world_vertices(opposing.get_transform())]
    release=max(v[0] for v in opponent_vertices)<-10
    follower_speed=follower.get_velocity().length()
    reciprocal_stop=release and cfg.get('reciprocal_yield',True)
    follower.apply_control(carla.VehicleControl(throttle=0 if reciprocal_stop else max(0,min(.45,.22*(5-follower_speed))),brake=1 if reciprocal_stop else 0))
    requested=command(ego,route,cfg['requested_speed_mps'])
    if cfg.get('ignore_yield',False):release=True
    if not release:requested['control'].update(throttle=0,brake=1,steer=0)
    ego.apply_control(carla.VehicleControl(**requested['control']))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-started;originals={}
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Unsynchronized original camera '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]={'frame':frame,'sha256':hashlib.sha256(image.raw_data).hexdigest()}
    transform=ego.get_transform();vertices=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(transform)];wp=mapping.get_waypoint(transform.location)
    opponent_vertices=[[v.x,v.y,v.z] for v in opposing.bounding_box.get_world_vertices(opposing.get_transform())]
    interactions.write(json.dumps({'frame':frame,'time_s':now,'subject_body_vertices_m':vertices,'opposing_body_vertices_m':opponent_vertices,
     'reciprocal_body_vertices_m':[[v.x,v.y,v.z] for v in follower.bounding_box.get_world_vertices(follower.get_transform())],'reciprocal_speed_mps':follower.get_velocity().length(),'reciprocal_yield_command':reciprocal_stop,
     'subject_speed_mps':ego.get_velocity().length(),'opposing_speed_mps':opposing.get_velocity().length(),
     'subject_left_indicator_bit':bool(ego.get_light_state() & carla.VehicleLightState.LeftBlinker),
     'opposing_road_id':mapping.get_waypoint(opposing.get_transform().location).road_id,'ego_release_observed':release})+'\n')
    body.write(json.dumps({'frame':frame,'time_s':now,'body_vertices_m':vertices,'road_id':None if wp is None else wp.road_id,
     'lane_id':None if wp is None else wp.lane_id,'control':requested,'camera_originals':originals})+'\n')
    capture.capture(frame,now);fmap.append(frame,now);frames+=1
  if frames!=cfg['duration_s']*cfg['rate_hz']:raise ValueError('Incomplete original duration')
 except BaseException as error:errors.append({'message':str(error),'traceback':traceback.format_exc()})
 finally:
  if capture:
   try:capture.close(confirmed=not errors and frames==cfg['duration_s']*cfg['rate_hz'])
   except BaseException as error:errors.append({'capture_close':str(error)})
  for process in encoders.values():
   try:process.stdin.close();code=process.wait(timeout=180);assert code==0
   except BaseException as error:errors.append({'encoder':str(error)})
  for stream in streams.values():stream.close()
  for actor in reversed(owned):
   try:actor.destroy()
   except BaseException as error:errors.append({'destroy':str(error)})
  try:restoration=restore(client,saved)
  except BaseException as error:errors.append({'restore':str(error)});restoration={'restored':False}
  (out/'native-run-status.json').write_text(json.dumps({'frames':frames,'errors':errors,'restoration':restoration},indent=2)+'\n')
 if errors:raise RuntimeError('Native capture failed: '+str(errors))
 receipt=compose_four_views({name:out/(name+'.mkv') for name in queues},out/'video_frames.jsonl',out/'raw.mkv')
 (out/'four-view-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 finalize(out,out/'analysis-report.json')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir',default='.')
 p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000);a=p.parse_args()
 if a.check:print(json.dumps(check()))
 else:run(a)
