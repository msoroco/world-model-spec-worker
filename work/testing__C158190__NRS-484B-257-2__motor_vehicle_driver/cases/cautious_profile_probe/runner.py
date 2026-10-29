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
 signals=west.findall('./signals/signal');assert signals
 assert any(s.get('type') in ('205','206','1000001') for s in signals)
 assert cfg['duration_s']==45 and cfg['rate_hz']==20 and cfg['required_atoms']==['kin.speed','st.one_way_roadway']
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
  from entrance_controls import spawn_markings,setup_governance,observe_governance
  markings=spawn_markings(carla,world,cfg);owned.extend(markings)
  marking_inventory=[{'actor_id':a.id,'type_id':a.type_id,'position_m':[a.get_location().x,a.get_location().y,a.get_location().z]} for a in markings]
  map_=world.get_map();west=map_.get_waypoint_xodr(1,-1,365);north=map_.get_waypoint_xodr(4,1,35)
  if west is None or north is None:raise ValueError('Missing connected west/north approach lane')
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','subject_west_entrance');ego=world.spawn_actor(bp,west.transform);owned.append(ego)
  bp2=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp2.set_attribute('role_name','through_north_vehicle');through=world.spawn_actor(bp2,north.transform);owned.append(through)
  governance=setup_governance(carla,world,map_,cfg,owned)
  for vehicle in (ego,through):vehicle.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for _ in range(20):world.tick()
  landmarks=[{'id':x.id,'road_id':x.road_id,'type':x.type,'name':x.name} for x in map_.get_all_landmarks()]
  context={'mode':cfg['mode'],'west_entrance_road_id':1,'through_entrance_road_id':4,'junction_id':100,
   'map_landmarks':landmarks,'physical_stopline_tiles':marking_inventory,
   'actual_officer_signal_control':{'requested':cfg['governing_active'],'kind':cfg['control_kind'],'readback_source':'interaction_history.jsonl governing_control_observation'},'reference_kind':cfg['reference_kind'],'stopping_reference_x_m':cfg['stopping_reference_x_m'],'other_entrance_obligation':cfg['other_entrance_obligation'],'non_through_highway':cfg['non_through_highway'],'physical_region_definition':cfg['reference_kind'],'driver_context':{'ordinary_vehicle':'vehicle.lincoln.mkz_2020','actual_physical_control':'Authored conventional driver control; original actuation retained'},
   'stopline_present':cfg['reference_kind']=='marked_stop_line','crosswalk_present':'crosswalk' in cfg['reference_kind'],
   'sign_authorization':'Synthetic authored sign; original pixel and actual governance verification pending'}
  (out/'control_context.json').write_text(json.dumps(context,indent=2)+'\n')
  (out/'scenario_geometry.json').write_text(json.dumps({'source':'authored one-way west and two-way crossroad with Native map readback','physical_verification':{'map':'road.xodr','governance':'control_context.json'},'directed_roadways':[{'polygon':[[-400,-7],[7,-7],[7,0],[-400,0]],'direction_xy':[1,0],'one_way':True}],'intersection_polygon':[[-7,-7],[7,-7],[7,7],[-7,7]]}))
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
    observation=observe_governance(carla,world,governance,cfg,i)
    active=observation.get('controls_subject',False)
    may_depart=(through_clear or cfg['ignore_other_priority']) and i>=cfg['minimum_release_tick']
    if active:may_depart=observation.get('direction')=='proceed' or observation.get('signal_state')=='Green'
    target_x=30 if may_depart else cfg['stopping_reference_x_m']-2.5
    desired=min(cfg['departure_speed_mps'] if may_depart else 6,max(0,(target_x-e_before['position_m'][0])*.6))
    if cfg['initial_response']=='none' and not active:desired=cfg['departure_speed_mps']
    if cfg['initial_response']=='stopped' and not may_depart and e_before['position_m'][0]>cfg['stopping_reference_x_m']-3:desired=0
    e_speed=e_before['speed_mps'];t_speed=t_before['speed_mps']
    ego.apply_control(carla.VehicleControl(throttle=max(0,min(.55,.4*(desired-e_speed))),brake=max(0,min(.8,.5*(e_speed-desired)))))
    through_desired=7 if cfg['through_start_tick']<=i<cfg['through_start_tick']+600 else 0
    through.apply_control(carla.VehicleControl(throttle=max(0,min(.6,.4*(through_desired-t_speed))),brake=max(0,min(.8,.3*(t_speed-through_desired)))))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start;originals={}
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Original camera tick mismatch: '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]=hashlib.sha256(image.raw_data).hexdigest()
    e,t=actor_state(ego),actor_state(through)
    history.write(json.dumps({'frame':frame,'time_s':now,'ego':e,'through':t,'ego_applied_control':{'throttle':ego.get_control().throttle,'brake':ego.get_control().brake},
     'governing_control_observation':observation,'through_clear':through_clear,'original_camera_sha256':originals})+'\n')
    if e['position_m'][0]<-7:
     eye=carla.Location(x=e['position_m'][0],y=e['position_m'][1],z=e['position_m'][2]+1.5);target=through.get_transform().location
     hits=world.cast_ray(eye,target);blockers=[h for h in hits if not ego.bounding_box.contains(h.location,ego.get_transform()) and not through.bounding_box.contains(h.location,through.get_transform())]
     viewpoints.write(json.dumps({'frame':frame,'time_s':now,'point_xy_m':e['position_m'][:2],
      'distance_to_intersection_m':max(0,-7-e['position_m'][0]),'clear_ray':not bool(blockers),'ray_hit_count':len(hits),'blocker_count':len(blockers),'original_ray_hits_m':[[h.location.x,h.location.y,h.location.z] for h in hits],
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
