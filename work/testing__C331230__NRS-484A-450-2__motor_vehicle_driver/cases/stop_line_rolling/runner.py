"""Original STOP approach with physical near-side crosswalk stripes."""
import argparse, hashlib, json, math, queue, subprocess, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot,restore
ROOT=Path(__file__).resolve().parent

def check():
 cfg=json.loads((ROOT/'config.json').read_text());tree=ET.parse(ROOT/'scene.xodr');root=tree.getroot()
 roads={r.get('id'):r for r in root.findall('road')};assert {'1','2','3','4','11'}<=set(roads)
 links=roads['11'].find('link');assert links.find('predecessor').get('elementId')=='1' and links.find('successor').get('elementId')=='2'
 assert roads['1'].find('signals/signal') is not None
 assert (ROOT/'crosswalk_markings.py').is_file()
 assert cfg['duration_s']==45 and cfg['rate_hz']==20
 assert [(c['name'],c['width'],c['height']) for c in cfg['cameras']]==[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]
 return {'passed':True,'stop_approach_connected':True,'stop_sign_declared':True,'crosswalk_mesh_builder_present':True,'physical_motion_verified':False}

def route_points(mapping):
 route=[]
 for road,stations in [(1,range(360,393,2)),(11,range(0,14,1)),(2,range(2,102,2))]:
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
 from crosswalk_markings import spawn as spawn_markings,observe as observe_markings
 client=carla.Client(args.host,args.port);client.set_timeout(60);saved=snapshot(client)
 out=Path(args.output_dir);cfg=json.loads((ROOT/'config.json').read_text());owned=[];encoders={};streams={};queues={};capture=None;errors=[];frames=0
 try:
  world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text());settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
  world.set_weather(carla.WeatherParameters.ClearNoon);mapping=world.get_map();route=route_points(mapping)
  markings=spawn_markings(carla,world,cfg);owned.extend(markings)
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','stop_crosswalk_subject')
  wp=mapping.get_waypoint_xodr(1,-1,350);ego=world.spawn_actor(bp,wp.transform);owned.append(ego)
  ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for _ in range(20):world.tick()
  tiles=observe_markings(markings);vertices=[v for tile in tiles for v in tile['body_vertices_m']]
  mode=cfg['stop_reference'];boundary=-13 if mode=='marked_crosswalk' else -10 if mode=='unmarked_crosswalk' else -11 if mode=='stop_line' else -7.5
  if tiles:boundary=min(v[0] for v in vertices)
  sight=[]
  if mode=='nearest_sight':
   for i in range(70):
    x=-25+i*.25;eye=carla.Location(x=x,y=1.75,z=1.5);rays=[]
    for target in [carla.Location(x=1.75,y=80,z=1.5),carla.Location(x=-1.75,y=-80,z=1.5)]:
     hits=[{'location_m':[h.location.x,h.location.y,h.location.z],'label':str(h.label)} for h in world.cast_ray(eye,target)]
     rays.append({'target_m':[target.x,target.y,target.z],'hits':hits,'clear':not hits})
    sight.append({'source_frame':world.get_snapshot().frame,'candidate_eye_m':[eye.x,eye.y,eye.z],'rays':rays})
   clear=[p for p in sight if all(r['clear'] for r in p['rays'])]
   if not clear:raise ValueError('No sampled visible stopping reference before intersection')
   boundary=max(p['candidate_eye_m'][0] for p in clear)
  (out/'sight_samples.json').write_text(json.dumps({'samples':sight,'resolution_m':.25,'scope':'finite collision rays; no continuous nearest point or optical visibility proof'})+'\n')
  geometry={'source':'Native physical markings and stop-sign readback; unmarked crosswalk from authored sidewalk prolongations; finite original ray scan',
   'crosswalk_upstream_x_m':boundary,'crosswalk_downstream_x_m':boundary+3 if 'crosswalk' in mode else boundary,
   'crosswalk_physical_tile_count':len(tiles),'physical_marking_inventory':tiles,
   'stop_sign_landmarks':[{'id':str(l.id),'road_id':l.road_id,'type':l.type} for l in mapping.get_all_landmarks() if str(l.type)=='206'],
   'governed_approach_road_id':1,'branch':mode,'stopline_also_present':mode=='stop_line',
   'unmarked_sidewalk_prolongations_m':{'upstream_x':-10,'downstream_x':-7} if mode=='unmarked_crosswalk' else {},
   'public_highway_designation':'synthetic authored assumption; factual status unverified'}
  (out/'crosswalk_geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
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
  started=world.get_snapshot().timestamp.elapsed_seconds;dwell=0;released=False
  with FrameMap(out/'video_frames.jsonl') as fmap,(out/'stop_history.jsonl').open('x') as stop:
   for i in range(cfg['duration_s']*cfg['rate_hz']):
    requested=command(ego,route,cfg['requested_speed_mps'])
    before_vertices=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(ego.get_transform())]
    front=max(v[0] for v in before_vertices);speed=ego.get_velocity().length()
    if not released and not cfg.get('rolling_probe',False):
     margin=geometry['crosswalk_upstream_x_m']-2-front
     target=min(cfg['requested_speed_mps'],math.sqrt(max(0,2*1.2*margin)))
     requested['control'].update(throttle=max(0,min(.45,.3*(target-speed))),brake=max(0,min(1,.45*(speed-target))),steer=0)
     if margin<=.2 and speed<.08:dwell+=1
     else:dwell=0
     if dwell>=40:released=True
    ego.apply_control(carla.VehicleControl(**requested['control']))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-started;originals={}
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Unsynchronized original camera '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]={'frame':frame,'sha256':hashlib.sha256(image.raw_data).hexdigest()}
    transform=ego.get_transform();vertices=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(transform)];wp=mapping.get_waypoint(transform.location)
    stop.write(json.dumps({'frame':frame,'time_s':now,'body_vertices_m':vertices,'speed_mps':ego.get_velocity().length(),
     'road_id':None if wp is None else wp.road_id,'lane_id':None if wp is None else wp.lane_id,
     'dwell_ticks':dwell,'released':released,'control':requested,'camera_originals':originals})+'\n')
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
