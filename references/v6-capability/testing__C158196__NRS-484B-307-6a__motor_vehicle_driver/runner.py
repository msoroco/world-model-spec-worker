"""Original Native yellow-to-red signal sequence and full-body intersection entry."""
import argparse,hashlib,json,queue,subprocess,traceback,xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot,restore
ROOT=Path(__file__).resolve().parent

def check():
 cfg=json.loads((ROOT/'config.json').read_text());root=ET.parse(ROOT/'scene.xodr').getroot()
 west=root.find("road[@id='1']");cross=root.find("road[@id='3']")
 assert root.find("junction[@id='100']") is not None and west is not None and cross is not None
 assert west.find('./signals/signal[@type="1000001"]') is not None
 assert all(l.get('type')!='driving' for l in west.findall('./lanes/laneSection/left/lane'))
 assert any(l.get('type')=='driving' for l in cross.findall('./lanes/laneSection/left/lane'))
 assert any(l.get('type')=='driving' for l in cross.findall('./lanes/laneSection/right/lane'))
 assert cfg['duration_s']==45 and cfg['rate_hz']==20
 assert cfg['source_packets']==['scenario_geometry']
 assert [(c['name'],c['width'],c['height']) for c in cfg['cameras']]==[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]
 return {'passed':True,'west_one_way':True,'cross_two_way':True,'signal_declared':True,'carla_contacted':False}

def state(actor):
 t=actor.get_transform();v=actor.get_velocity()
 return {'actor_id':actor.id,'position_m':[t.location.x,t.location.y,t.location.z],'velocity_mps':[v.x,v.y,v.z],
  'speed_mps':v.length(),'body_vertices_m':[[p.x,p.y,p.z] for p in actor.bounding_box.get_world_vertices(t)]}

def run(args):
 import carla
 from pipeline_capture import PipelineCapture
 from analyze import finalize
 cfg=json.loads((ROOT/'config.json').read_text());out=Path(args.output_dir)
 client=carla.Client(args.host,args.port);client.set_timeout(90);saved=snapshot(client)
 owned=[];encoders={};streams={};queues={};cameras={};capture=None;frames=0;errors=[]
 try:
  world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text())
  settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
  map_=world.get_map();west=map_.get_waypoint_xodr(1,-1,323)
  if west is None:raise ValueError('Native west lane missing')
  heads=[a for a in world.get_actors() if a.type_id.startswith('traffic.traffic_light')]
  west_heads=[a for a in heads if getattr(a,'get_opendrive_id',lambda:'' )()=='3076']
  if len(west_heads)!=1:raise ValueError('Exactly one installed Native west vehicular signal head required')
  signal=west_heads[0];signal.freeze(True)
  affected=[[w.road_id,w.section_id,w.lane_id] for w in signal.get_affected_lane_waypoints()]
  if not any(v[0]==1 and v[2] in (-1,-2) for v in affected):raise ValueError('Native signal does not govern west approach')
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','subject_west_yellow')
  ego=world.spawn_actor(bp,west.transform);owned.append(ego);ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for _ in range(20):world.tick()
  context={'west_signal_actor_id':signal.id,'native_opendrive_id':signal.get_opendrive_id(),'affected_lanes':affected,
   'vehicle_heads':[{'actor_id':a.id,'opendrive_id':a.get_opendrive_id()} for a in heads],
   'pedestrian_heads':[{'actor_id':a.id,'type_id':a.type_id} for a in world.get_actors() if 'pedestrian' in a.type_id and 'traffic' in a.type_id],
   'intersection_edge_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],
   'route':'road1 lane-1 through junction connector11 to road2 lane-1; Native readback and physical completion pending',
   'official_device_provenance':'Synthetic authored OpenDRIVE device; authorization not established',
   'entry_reference':'first full-body polygon overlap with roadway-edge intersection, 20Hz sampled'}
  (out/'signal_context.json').write_text(json.dumps(context,indent=2)+'\n')
  (out/'scenario_geometry.json').write_text(json.dumps({'source':'authored one-way west/two-way crossroad; Native map readback required',
   'physical_verification':{'map':'road.xodr','original_signal':'signal_context.json'},
   'directed_roadways':[{'polygon':[[-400,-7],[7,-7],[7,0],[-400,0]],'direction_xy':[1,0],'one_way':True}],
   'intersection_polygon':[[-7,-7],[7,-7],[7,7],[-7,7]]},indent=2)+'\n')
  for spec in cfg['cameras']:
   name,w,h=spec['name'],spec['width'],spec['height'];cbp=world.get_blueprint_library().find('sensor.camera.rgb')
   for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:cbp.set_attribute(key,str(value))
   if name=='overview':pose=carla.Transform(carla.Location(x=-5,y=0,z=90),carla.Rotation(pitch=-90));attach=None
   elif name=='approach':pose=carla.Transform(carla.Location(x=-9,y=0,z=8),carla.Rotation(pitch=-10));attach=ego
   elif name=='reference_corner':pose=carla.Transform(carla.Location(x=-15,y=-12,z=19),carla.Rotation(pitch=-40));attach=None
   else:pose=carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation());attach=ego
   camera=world.spawn_actor(cbp,pose,attach_to=attach);owned.append(camera);cameras[name]=camera;queues[name]=queue.Queue();camera.listen(queues[name].put)
   stream=(out/(name+'.encoder.log')).open('x');streams[name]=stream
   encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra','-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=stream)
  capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
  start=world.get_snapshot().timestamp.elapsed_seconds
  with FrameMap(out/'video_frames.jsonl') as fmap,(out/'signal_history.jsonl').open('x') as history:
   for i in range(cfg['duration_s']*20):
    desired=carla.TrafficLightState.Green if i<120 or i>=400 else carla.TrafficLightState.Yellow if i<200 else carla.TrafficLightState.Red
    signal.set_state(desired)
    before=state(ego);x=before['position_m'][0];speed=before['speed_mps']
    goal=(-13 if 200<=i<400 else 30)
    requested=min(3.5,max(0,(goal-x)*.45))
    ego.apply_control(carla.VehicleControl(throttle=max(0,min(.55,.4*(requested-speed))),brake=max(0,min(.8,.45*(speed-requested)))))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start;originals={}
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Original camera tick mismatch: '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]=hashlib.sha256(image.raw_data).hexdigest()
    actual=signal.get_state();e=state(ego)
    history.write(json.dumps({'frame':frame,'time_s':now,'ego':e,'signal_actor_id':signal.id,'signal_state':str(actual).split('.')[-1],
      'requested_state':str(desired).split('.')[-1],'affected_lanes':affected,'camera_original_sha256':originals})+'\n')
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
