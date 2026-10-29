"""Original Native west-entrance yield/stop interaction; four synchronized views."""
import argparse,hashlib,json,queue,subprocess,traceback,xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot,restore
ROOT=Path(__file__).resolve().parent

def check():
 cfg=json.loads((ROOT/'config.json').read_text());root=ET.parse(ROOT/'scene.xodr').getroot();west=root.find("road[@id='1']")
 assert west is not None and root.find("junction[@id='100']") is not None
 signals=west.findall('./signals/signal');assert len(signals)==1
 assert signals[0].get('type')==('205' if cfg['mode']=='yield_nearest' else '206')
 if cfg['mode']=='yield_nearest':assert not root.findall('.//object') and not root.findall('.//road[@id="1"]//object')
 else:assert west.findall('./objects/object')
 assert cfg['duration_s']==45 and cfg['rate_hz']==20 and cfg['required_atoms']==['kin.speed']
 assert [(c['name'],c['width'],c['height']) for c in cfg['cameras']]==[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]
 return {'passed':True,'selected_mode':cfg['mode'],'connected_junction':True,'carla_contacted':False}

def actor_state(actor):
 t=actor.get_transform();v=actor.get_velocity();return {'actor_id':actor.id,'position_m':[t.location.x,t.location.y,t.location.z],
 'velocity_mps':[v.x,v.y,v.z],'speed_mps':v.length(),'body_vertices_m':[[p.x,p.y,p.z] for p in actor.bounding_box.get_world_vertices(t)]}

def run(args):
 import carla
 from pipeline_capture import PipelineCapture
 from analyze import finalize
 cfg=json.loads((ROOT/'config.json').read_text());out=Path(args.output_dir);client=carla.Client(args.host,args.port);client.set_timeout(90);saved=snapshot(client)
 owned=[];encoders={};streams={};queues={};cameras={};capture=None;frames=0;errors=[]
 try:
  world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text());settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
  if cfg['mode']=='stop_within':
   from physical_stopline import spawn,observe
   markings=spawn(carla,world);owned.extend(markings)
   for _ in range(3):world.tick()
   marking_inventory=observe(markings)
  else:marking_inventory=[]
  map_=world.get_map();west=map_.get_waypoint_xodr(1,-1,365);north=map_.get_waypoint_xodr(4,1,35)
  if west is None or north is None:raise ValueError('Missing connected west/north approach lane')
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','subject_west_entrance');ego=world.spawn_actor(bp,west.transform);owned.append(ego)
  bp2=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp2.set_attribute('role_name','through_north_vehicle');through=world.spawn_actor(bp2,north.transform);owned.append(through)
  for vehicle in (ego,through):vehicle.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for _ in range(20):world.tick()
  landmarks=[{'id':x.id,'road_id':x.road_id,'type':x.type,'name':x.name} for x in map_.get_all_landmarks()]
  context={'mode':cfg['mode'],'west_entrance_road_id':1,'through_entrance_road_id':4,'junction_id':100,
   'map_landmarks':landmarks,'physical_stopline_tiles':marking_inventory,
   'actual_officer_signal_control':'No officer or signal actor spawned; full world inventory required',
   'stopline_present':cfg['mode']=='stop_within','crosswalk_present':False,
   'sign_authorization':'Synthetic authored sign; original pixel and actual governance verification pending'}
  (out/'control_context.json').write_text(json.dumps(context,indent=2)+'\n')
  for spec in cfg['cameras']:
   name,w,h=spec['name'],spec['width'],spec['height'];cbp=world.get_blueprint_library().find('sensor.camera.rgb')
   for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:cbp.set_attribute(key,str(value))
   if name=='overview':pose=carla.Transform(carla.Location(x=-2,y=0,z=85),carla.Rotation(pitch=-90));attach=None
   elif name=='approach':pose=carla.Transform(carla.Location(x=-9,y=0,z=7),carla.Rotation(pitch=-10));attach=ego
   elif name=='reference_corner':pose=carla.Transform(carla.Location(x=-11,y=-17,z=22),carla.Rotation(pitch=-50));attach=None
   else:pose=carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation());attach=ego
   camera=world.spawn_actor(cbp,pose,attach_to=attach);owned.append(camera);cameras[name]=camera;queues[name]=queue.Queue();camera.listen(queues[name].put)
   stream=(out/(name+'.encoder.log')).open('x');streams[name]=stream
   encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra','-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=stream)
  capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
  start=world.get_snapshot().timestamp.elapsed_seconds
  with FrameMap(out/'video_frames.jsonl') as fmap,(out/'interaction_history.jsonl').open('x') as history,(out/'view_samples.jsonl').open('x') as viewpoints:
   for i in range(cfg['duration_s']*20):
    e_before,t_before=actor_state(ego),actor_state(through)
    through_clear=max(v[1] for v in t_before['body_vertices_m'])<-9
    target_x=30 if through_clear else (-10.5 if cfg['mode']=='yield_nearest' else -13)
    desired=min(6,max(0,(target_x-e_before['position_m'][0])*.6));if_stop=cfg['mode']=='stop_within' and not through_clear
    if if_stop and e_before['position_m'][0]>-14:desired=0
    e_speed=e_before['speed_mps'];t_speed=t_before['speed_mps']
    ego.apply_control(carla.VehicleControl(throttle=max(0,min(.55,.4*(desired-e_speed))),brake=max(0,min(.8,.5*(e_speed-desired)))))
    through_desired=7 if i<600 else 0
    through.apply_control(carla.VehicleControl(throttle=max(0,min(.6,.4*(through_desired-t_speed))),brake=max(0,min(.8,.3*(t_speed-through_desired)))))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start;originals={}
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Original camera tick mismatch: '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]=hashlib.sha256(image.raw_data).hexdigest()
    e,t=actor_state(ego),actor_state(through)
    history.write(json.dumps({'frame':frame,'time_s':now,'ego':e,'through':t,'ego_applied_control':{'throttle':ego.get_control().throttle,'brake':ego.get_control().brake},
     'through_clear':through_clear,'original_camera_sha256':originals})+'\n')
    if cfg['mode']=='yield_nearest' and e['position_m'][0]<-7:
     eye=carla.Location(x=e['position_m'][0],y=e['position_m'][1],z=e['position_m'][2]+1.5);target=through.get_transform().location
     hits=world.cast_ray(eye,target)
     viewpoints.write(json.dumps({'frame':frame,'time_s':now,'point_xy_m':e['position_m'][:2],
      'distance_to_intersection_m':max(0,-7-e['position_m'][0]),'clear_ray':not bool(hits),'ray_hit_count':len(hits),
      'target_actor_id':through.id})+'\n')
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
