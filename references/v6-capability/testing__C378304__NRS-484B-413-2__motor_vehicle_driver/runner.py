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
 assert {'1','2','3','4','14'}<=set(roads)
 arc=roads['14'].find('planView/geometry/arc')
 assert arc is not None and abs(float(arc.get('curvature'))+1/7)<1e-6
 links=roads['14'].find('link');assert links.find('predecessor').get('elementId')=='1' and links.find('successor').get('elementId')=='3'
 assert root.find('.//object[@id="4132001"]') is not None
 assert cfg['duration_s']==50 and cfg['rate_hz']==20
 assert [(c['name'],c['width'],c['height']) for c in cfg['cameras']]==[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]
 return {'passed':True,'right_turn_connector':True,'loading_zone_boundary_authored':True,'native_motion_verified':False}

def route_points(mapping):
 route=[]
 for road,stations,lane in [(1,range(280,393,2),-1),(14,[i*10.995574287564276/20 for i in range(21)],-1),(3,range(393,339,-2),1)]:
  for station in stations:
   wp=mapping.get_waypoint_xodr(road,lane,float(station))
   if wp is None:raise ValueError('Native right-turn lane connection missing')
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
 from worker_exchange.optical_measurements import project_body,photometry
 client=carla.Client(args.host,args.port);client.set_timeout(60);saved=snapshot(client)
 out=Path(args.output_dir);cfg=json.loads((ROOT/'config.json').read_text());owned=[];encoders={};streams={};queues={};cameras={};capture=None;errors=[];frames=0
 try:
  world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text());settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
  world.set_weather(carla.WeatherParameters.ClearNoon);mapping=world.get_map();route=route_points(mapping)
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','business_district_right_turn_subject')
  wp=mapping.get_waypoint_xodr(1,-1,280);ego=world.spawn_actor(bp,wp.transform);owned.append(ego)
  ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  ego.set_light_state(carla.VehicleLightState.RightBlinker)
  for _ in range(20):world.tick()
  geometry={'source':'Native OpenDRIVE map and authored district/loading context','approach_road_id':1,'departure_road_id':3,
   'connector_road_id':14,'right_turn_arc_curvature_per_m':-1/7,'route_waypoints_native_xy':route,
   'business_district_frontage_m':120,'business_use_frontage_m':90,
   'loading_zone_polygon':[[-50,-10],[-25,-10],[-25,-7],[-50,-7]],
   'district_source':'synthetic authored business frontage; actual statutory status remains external',
   'loading_zone_designation_source':'synthetic freight loading designation and OpenDRIVE object 4132001'}
  (out/'road_geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
  for spec in cfg['cameras']:
   name,w,h=spec['name'],spec['width'],spec['height'];camera_bp=world.get_blueprint_library().find('sensor.camera.rgb')
   for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:camera_bp.set_attribute(key,str(value))
   if name=='overview':pose=carla.Transform(carla.Location(x=0,y=0,z=60),carla.Rotation(pitch=-90));attached=ego
   elif name=='approach':pose=carla.Transform(carla.Location(x=-8,y=0,z=5),carla.Rotation(pitch=-15));attached=ego
   elif name=='reference_corner':pose=carla.Transform(carla.Location(x=-18,y=18,z=28),carla.Rotation(pitch=-40,yaw=-120));attached=None
   else:pose=carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation());attached=ego
   camera=world.spawn_actor(camera_bp,pose,attach_to=attached);owned.append(camera);cameras[name]=camera;queues[name]=queue.Queue();camera.listen(queues[name].put)
   streams[name]=(out/(name+'.encoder.log')).open('x');encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra','-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=streams[name])
  capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
  started=world.get_snapshot().timestamp.elapsed_seconds
  with FrameMap(out/'video_frames.jsonl') as fmap,(out/'body_history.jsonl').open('x') as body,(out/'signal_history.jsonl').open('x') as signals:
   for i in range(cfg['duration_s']*cfg['rate_hz']):
    requested=command(ego,route,cfg['requested_speed_mps']);ego.apply_control(carla.VehicleControl(**requested['control']))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-started;originals={};optical=None
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Unsynchronized original camera '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]={'frame':frame,'sha256':hashlib.sha256(image.raw_data).hexdigest()}
     if name=='reference_corner':
      try:
       t=ego.get_transform();verts=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(t)]
       roi=project_body(verts,cameras[name].get_transform().get_inverse_matrix(),w,h,spec['fov_deg'])
       optical={'body_roi':roi,'photometry':photometry(image.raw_data,w,h,roi),'camera_frame':image.frame}
      except ValueError:optical={'body_roi_available':False,'camera_frame':image.frame}
    transform=ego.get_transform();vertices=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(transform)];wp=mapping.get_waypoint(transform.location)
    body.write(json.dumps({'frame':frame,'time_s':now,'body_vertices_m':vertices,'road_id':None if wp is None else wp.road_id,
     'lane_id':None if wp is None else wp.lane_id,'control':requested,'camera_originals':originals})+'\n')
    signals.write(json.dumps({'frame':frame,'time_s':now,'right_indicator_api_bit':bool(ego.get_light_state() & carla.VehicleLightState.RightBlinker),
     'body_roi_photometry':optical,'road_id':None if wp is None else wp.road_id,'position_m':[transform.location.x,transform.location.y,transform.location.z]})+'\n')
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
 rows=[json.loads(line) for line in (out/'signal_history.jsonl').read_text().splitlines() if line]
 onset=next((i for i,r in enumerate(rows) if r['road_id']==14),None)
 if onset is None or onset<2:raise ValueError('Native right-turn onset not observed')
 approach=rows[:onset+1]
 packet={'law_id':cfg['law_id'],'diagnostic_fixture_only':False,'road_id':1,
   'frontage_m':geometry['business_district_frontage_m'],'business_use_frontage_m':geometry['business_use_frontage_m'],
   'district_source':geometry['district_source'],'turn_onset_frame':rows[onset]['frame'],
   'path_rows':[{'x_m':r['position_m'][0],'y_m':r['position_m'][1]} for r in approach],
   'indicator_rows':[{'frame':r['frame'],'lamp_bits':int(r['right_indicator_api_bit']),
      'pixel_luminance':None if not r['body_roi_photometry'] or not r['body_roi_photometry'].get('photometry')
        else r['body_roi_photometry']['photometry']['mean_luminance']} for r in approach],
   'zone_polygon':geometry['loading_zone_polygon'],'zone_route_distance_m':6,
   'zone_designation_source':geometry['loading_zone_designation_source']}
 (out/'case_observation.json').write_text(json.dumps(packet,indent=2)+'\n')
 finalize(out,out/'analysis-report.json')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir',default='.')
 p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000);a=p.parse_args()
 if a.check:print(json.dumps(check()))
 else:run(a)
