"""Original Native mountain curve U-turn attempt and both-direction sight rays."""
import argparse,hashlib,json,math,queue,subprocess,traceback,xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot,restore
ROOT=Path(__file__).resolve().parent

def check():
 cfg=json.loads((ROOT/'config.json').read_text());root=ET.parse(ROOT/'scene.xodr').getroot();road=root.find("road[@id='1']")
 assert road is not None and float(road.get('length'))==1500
 arcs=road.findall('./planView/geometry/arc');assert len(arcs)==1 and abs(float(arcs[0].get('curvature'))-.004)<1e-9
 assert len(road.findall('.//lane[@type="driving"]'))==2 and len(road.findall('./elevationProfile/elevation'))>=3
 assert cfg['duration_s']==45 and cfg['rate_hz']==20 and cfg['required_atoms']==['kin.speed']
 assert [(c['name'],c['width'],c['height']) for c in cfg['cameras']]==[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]
 return {'passed':True,'curve_per_m':.004,'crest_profile':True,'carla_contacted':False}

def run(args):
 import carla
 from pipeline_capture import PipelineCapture
 from analyze import finalize
 cfg=json.loads((ROOT/'config.json').read_text());out=Path(args.output_dir);client=carla.Client(args.host,args.port);client.set_timeout(90);saved=snapshot(client)
 owned=[];encoders={};streams={};queues={};cameras={};capture=None;frames=0;errors=[]
 try:
  world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text());settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon);map_=world.get_map()
  actors={}
  for role,lane,station in [('ego',-1,650),('ahead_opposing',1,760),('behind_same_direction',-1,530)]:
   wp=map_.get_waypoint_xodr(1,lane,station)
   if wp is None:raise ValueError('Mountain curve lane missing: '+role)
   bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name',role)
   actor=world.spawn_actor(bp,wp.transform);owned.append(actor);actors[role]=actor;actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for _ in range(20):world.tick()
  (out/'curve_context.json').write_text(json.dumps({'native_road_id':1,'native_map_name':map_.name,'curvature_per_m':.004,'arc_station_m':[600,900],
   'elevation_profile_source':'scene.xodr station 650..850 crest','surface':'synthetic mountain road, Native actual terrain/occlusion pending',
   'driver_eye_height_m':1.5,'visibility_reference_ft':500,'visibility_reference_m':152.4},indent=2)+'\n')
  for spec in cfg['cameras']:
   name,w,h=spec['name'],spec['width'],spec['height'];cbp=world.get_blueprint_library().find('sensor.camera.rgb')
   for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:cbp.set_attribute(key,str(value))
   if name=='overview':pose=carla.Transform(carla.Location(x=700,y=30,z=150),carla.Rotation(pitch=-90));attach=None
   elif name=='approach':pose=carla.Transform(carla.Location(x=-12,y=0,z=8),carla.Rotation(pitch=-15));attach=actors['ego']
   elif name=='reference_corner':pose=carla.Transform(carla.Location(x=700,y=-35,z=55),carla.Rotation(pitch=-60));attach=None
   else:pose=carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation());attach=actors['ego']
   camera=world.spawn_actor(cbp,pose,attach_to=attach);owned.append(camera);cameras[name]=camera;queues[name]=queue.Queue();camera.listen(queues[name].put)
   stream=(out/(name+'.encoder.log')).open('x');streams[name]=stream
   encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra','-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=stream)
  ego=actors['ego'];capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
  start=world.get_snapshot().timestamp.elapsed_seconds;initial_yaw=ego.get_transform().rotation.yaw;previous_yaw=initial_yaw;turn_degrees=0;turn_started=False
  with FrameMap(out/'video_frames.jsonl') as fmap,(out/'turn_history.jsonl').open('x') as motion,(out/'visibility_samples.jsonl').open('x') as sight:
   for i in range(cfg['duration_s']*20):
    location=ego.get_transform().location;wp=map_.get_waypoint(location,project_to_road=True)
    if wp and wp.s>=685:turn_started=True
    speed=ego.get_velocity().length()
    if turn_started and abs(turn_degrees)<175:control=carla.VehicleControl(throttle=.23,steer=.7,brake=0)
    elif turn_started:control=carla.VehicleControl(brake=.7)
    else:control=carla.VehicleControl(throttle=max(0,min(.5,.35*(5-speed))),brake=max(0,min(.5,.2*(speed-5))))
    ego.apply_control(control)
    for role in ('ahead_opposing','behind_same_direction'):
     actor=actors[role];v=actor.get_velocity().length();actor.apply_control(carla.VehicleControl(throttle=max(0,min(.5,.3*(6-v))),brake=max(0,min(.5,.2*(v-6)))))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start;originals={}
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Original camera tick mismatch: '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]=hashlib.sha256(image.raw_data).hexdigest()
    t=ego.get_transform();yaw=t.rotation.yaw;turn_degrees+=(yaw-previous_yaw+180)%360-180;previous_yaw=yaw
    wp=map_.get_waypoint(t.location,project_to_road=True)
    motion.write(json.dumps({'frame':frame,'time_s':now,'road_station_m':None if wp is None else wp.s,'heading_deg':yaw,
     'cumulative_heading_change_deg':turn_degrees,'speed_mps':ego.get_velocity().length(),
     'body_vertices_m':[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(t)],'turn_started':turn_started,'original_camera_sha256':originals})+'\n')
    for role in ('ahead_opposing','behind_same_direction'):
     other=actors[role];ot=other.get_transform();owp=map_.get_waypoint(ot.location,project_to_road=True)
     eye=carla.Location(x=ot.location.x,y=ot.location.y,z=ot.location.z+1.5);target=carla.Location(x=t.location.x,y=t.location.y,z=t.location.z+1.5)
     hits=world.cast_ray(eye,target)
     sight.write(json.dumps({'frame':frame,'time_s':now,'approach':role,'other_actor_id':other.id,'subject_actor_id':ego.id,
      'route_distance_m':abs(owp.s-wp.s) if wp and owp else 9999,'clear_ray':not bool(hits),'ray_hit_count':len(hits),
      'observer_eye_m':[eye.x,eye.y,eye.z],'subject_target_m':[target.x,target.y,target.z]})+'\n')
    capture.capture(frame,now);fmap.append(frame,now);frames+=1
 except BaseException as error:errors.append({'message':str(error),'traceback':traceback.format_exc()})
 finally:
  if capture:
   try:capture.close(confirmed=not errors and frames==cfg['duration_s']*20)
   except BaseException as error:errors.append({'capture_close':str(error)})
  for process in encoders.values():
   try:
    process.stdin.close()
    if process.wait(timeout=180):errors.append({'encoder_exit':process.returncode})
   except BaseException as error:errors.append({'encoder':str(error)})
  for stream in streams.values():stream.close()
  for actor in reversed(owned):
   try:actor.destroy()
   except BaseException as error:errors.append({'destroy':str(error)})
  try:restoration=restore(client,saved)
  except BaseException as error:errors.append({'restore':str(error)});restoration={'restored':False}
  (out/'native-run-status.json').write_text(json.dumps({'frames':frames,'errors':errors,'restoration':restoration},indent=2)+'\n')
 if errors:raise RuntimeError('Native capture failed: '+str(errors))
 receipt=compose_four_views({name:out/(name+'.mkv') for name in cameras},out/'video_frames.jsonl',out/'raw.mkv')
 (out/'four-view-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 finalize(out,out/'analysis-report.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir',default='.')
 p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000);a=p.parse_args()
 if a.check:print(json.dumps(check()))
 else:run(a)
