"""One original Native left-turn episode on a connected two-way junction."""
import argparse, hashlib, json, math, queue, subprocess, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot,restore
ROOT=Path(__file__).resolve().parent

def check():
 cfg=json.loads((ROOT/'config.json').read_text());root=ET.parse(ROOT/'scene.xodr').getroot()
 roads={r.get('id'):r for r in root.findall('road')}
 assert {'1','2','3','4','11','12'}<=set(roads)
 assert len(root.findall('.//object[@type="barrier"]'))==2
 assert cfg['duration_s']==60 and cfg['rate_hz']==20
 assert {'kin.speed','kin.velocity','st.median_or_divider'}<=set(cfg['required_atoms'])
 assert [(c['name'],c['width'],c['height']) for c in cfg['cameras']]==[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]
 arc=[(-7+5.25*math.cos(-math.pi/2+math.pi*i/40),5.25*math.sin(-math.pi/2+math.pi*i/40)) for i in range(41)]
 assert all(-20<x<20 and -7<y<7 for x,y in arc)
 return {'passed':True,'median_opening_arc_in_polygon':True,'barrier_segments':2,'physical_motion_verified':False}

def route_points(mapping):
 cfg=json.loads((ROOT/"config.json").read_text());shift=cfg.get("crossing_shift_m",0)
 route=[]
 for station in range(300,394+int(shift),2):
  wp=mapping.get_waypoint_xodr(1,-2,float(station))
  if wp is None:raise ValueError('Native initial right-hand roadway lane missing')
  loc=wp.transform.location;route.append((loc.x,loc.y))
 route += [(-7+shift+5.25*math.cos(-math.pi/2+math.pi*i/40),5.25*math.sin(-math.pi/2+math.pi*i/40)) for i in range(41)]
 for station in range(393+int(shift),240,-2):
  wp=mapping.get_waypoint_xodr(1,2,float(station))
  if wp is None:raise ValueError('Native opposing roadway lane missing')
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
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','median_opening_uturn_subject')
  wp=mapping.get_waypoint_xodr(1,2 if cfg.get("wrong_initial_roadway",False) else -2,300);ego=world.spawn_actor(bp,wp.transform);owned.append(ego)
  ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for _ in range(20):world.tick()
  geometry={'source':'Native OpenDRIVE and authored median barrier readback','right_roadway_polygon':[[-400,-7],[-7,-7],[-7,-.5],[-400,-.5]],
    'opposing_roadway_polygon':[[-400,.5],[-7,.5],[-7,7],[-400,7]],
    'opening_polygon':[[-20,-.5],[20,-.5],[20,.5],[-20,.5]],'opening_width_m':40,
    'barrier_polygons':[[[-400,-.5],[-20,-.5],[-20,.5],[-400,.5]],[[20,-.5],[400,-.5],[400,.5],[20,.5]]],
    'route_waypoints_native_xy':route,'public_authority_established':False}
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
  with FrameMap(out/'video_frames.jsonl') as fmap,(out/'body_history.jsonl').open('x') as body:
   for i in range(cfg['duration_s']*cfg['rate_hz']):
    requested=command(ego,route,cfg['requested_speed_mps'])
    if cfg.get('pause_midturn',False) and 180<i<220:requested['control'].update(throttle=0,brake=1)
    ego.apply_control(carla.VehicleControl(**requested['control']))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-started;originals={}
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Unsynchronized original camera '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]={'frame':frame,'sha256':hashlib.sha256(image.raw_data).hexdigest()}
    transform=ego.get_transform();vertices=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(transform)];wp=mapping.get_waypoint(transform.location)
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
 rows=[json.loads(line) for line in (out/'trace.jsonl').read_text().splitlines() if line]
 bodies=[json.loads(line) for line in (out/'body_history.jsonl').read_text().splitlines() if line]
 moving=rows
 if len(moving)<2:raise ValueError('Native U-turn movement not observed')
 body_by_frame={r['frame']:r for r in bodies}
 trajectory=[]
 for row in moving:
  vertices=body_by_frame[row['frame']]['body_vertices_m']
  overlap=any(-20<v[0]<20 and -.5<v[1]<.5 for v in vertices)
  trajectory.append({'frame':row['frame'],'velocity_xy':row['velocity_mps'][:2],
    'body_overlaps_median':overlap,'body_vertices_m':vertices})
 packet={'law_id':cfg['law_id'],'diagnostic_fixture_only':False,
   'right_roadway_polygon':geometry['right_roadway_polygon'],'opposing_roadway_polygon':geometry['opposing_roadway_polygon'],
   'barrier_polygons':geometry['barrier_polygons'],'opening_polygon':geometry['opening_polygon'],
   'opening_width_m':geometry['opening_width_m'],'trajectory':trajectory,'opening_source_models':{'barrier': 'Physical barrier authored as two0.8m-high OpenDRIVE objects; actual rendering/collision requires Native audit', 'dividing_section': 'Non-roadway separating strip bounded by explicit median polygons', 'dividing_space': 'Exclusive dividing-space footprint between the opposing roadway boundaries; no legal numeric meaning assigned'},'divider_top_z_m':.8,'authority_context':cfg.get('authority_context',{'designation':'physical opening only','source':'authored test configuration; legal establishment unverified'})}
 packet['scope_context']={'highway_designation': 'Authored synthetic public highway; independent factual/legal jurisdiction review required', 'vehicle_blueprint': 'vehicle.lincoln.mkz_2020', 'controller_scope': 'Physical throttle/brake/steering commands on conventional vehicle; no automated-driving-system legal inference', 'cell_identity': 'C126120', 'fixed_layout': 'median_opening', 'fixed_maneuver': 'u_turn', 'fixed_control': 'median_barrier', 'source': 'Exact case config plus authored OpenDRIVE; actual public dedication/driver identity is not established by CPU fixture'}
 (out/'case_observation.json').write_text(json.dumps(packet,indent=2)+'\n')
 scenario={'source':'authored scene.xodr and Native road readback',
   'physical_verification':{'road_xodr':'road.xodr','body_history':'body_history.jsonl',
      'barrier_objects_authored':[250101,250102],'barrier_pixels_verified':False},
   'prohibited_median_polygons':geometry['barrier_polygons'],
   'median_opening_polygons':[geometry['opening_polygon']]}
 (out/'scenario_geometry.json').write_text(json.dumps(scenario,indent=2)+'\n')
 finalize(out,out/'analysis-report.json')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir',default='.')
 p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000);a=p.parse_args()
 if a.check:print(json.dumps(check()))
 else:run(a)
