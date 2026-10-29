"""Original backing across physical crosswalk stripes; four synchronized cameras."""
import argparse,hashlib,json,queue,subprocess,traceback,xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot,restore
ROOT=Path(__file__).resolve().parent

def check():
 cfg=json.loads((ROOT/'config.json').read_text());root=ET.parse(ROOT/'scene.xodr').getroot()
 assert root.find("road[@id='1']") is not None and root.find("junction[@id='100']") is not None
 assert not root.findall('.//signal') and not root.findall('.//object')
 assert cfg['duration_s']==35 and cfg['rate_hz']==20
 assert [(c['name'],c['width'],c['height']) for c in cfg['cameras']]==[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]
 assert cfg['required_atoms']==['kin.speed']
 return {'passed':True,'junction_connected':True,'crosswalk_physical_tiles_planned':True,'carla_contacted':False}

def run(args):
 import carla
 from pipeline_capture import PipelineCapture
 from crosswalk_markings import spawn,observe
 from analyze import finalize
 cfg=json.loads((ROOT/'config.json').read_text());out=Path(args.output_dir)
 client=carla.Client(args.host,args.port);client.set_timeout(90);saved=snapshot(client)
 owned=[];encoders={};streams={};queues={};cameras={};capture=None;frames=0;errors=[]
 try:
  world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text());settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
  world.set_weather(carla.WeatherParameters.ClearNoon)
  markings=spawn(carla,world,False);owned.extend(markings)
  for _ in range(3):world.tick()
  inventory=observe(markings)
  if len(inventory)!=80:raise ValueError('Incomplete physical crosswalk stripe inventory')
  (out/'crosswalk_context.json').write_text(json.dumps({'band_xy_m':[-8.45,-7.05,-7,7],
   'physical_marking_source':'Native static mesh stripe inventory and original pixel verification pending',
   'marking_actor_ids':[v['actor_id'] for v in inventory],'marking_asset':inventory[0]['asset'],
   'geometry_source':'scene.xodr and Native map road1/junction100','non_alley_intersection':True},indent=2)+'\n')
  wp=world.get_map().get_waypoint_xodr(1,1,380)
  if wp is None:raise ValueError('Westbound approach lane missing')
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','subject_backing_crosswalk')
  ego=world.spawn_actor(bp,wp.transform);owned.append(ego);ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for _ in range(20):world.tick()
  for spec in cfg['cameras']:
   name,w,h=spec['name'],spec['width'],spec['height'];cbp=world.get_blueprint_library().find('sensor.camera.rgb')
   for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:cbp.set_attribute(key,str(value))
   if name=='overview':pose=carla.Transform(carla.Location(x=0,y=0,z=60),carla.Rotation(pitch=-90));attach=ego
   elif name=='approach':pose=carla.Transform(carla.Location(x=-10,y=0,z=8),carla.Rotation(pitch=-20,yaw=180));attach=ego
   elif name=='reference_corner':pose=carla.Transform(carla.Location(x=-9,y=-18,z=22),carla.Rotation(pitch=-45));attach=None
   else:pose=carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation(yaw=180));attach=ego
   camera=world.spawn_actor(cbp,pose,attach_to=attach);owned.append(camera);cameras[name]=camera;queues[name]=queue.Queue();camera.listen(queues[name].put)
   stream=(out/(name+'.encoder.log')).open('x');streams[name]=stream
   encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra','-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=stream)
  capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
  start=world.get_snapshot().timestamp.elapsed_seconds
  with FrameMap(out/'video_frames.jsonl') as fmap,(out/'reverse_history.jsonl').open('x') as history:
   for i in range(cfg['duration_s']*20):
    before=ego.get_transform();speed=ego.get_velocity().length();remaining=cfg['reverse_target_x_m']-before.location.x
    desired=min(2.0,max(0,remaining*.6));effort=desired-speed
    ego.apply_control(carla.VehicleControl(reverse=True,throttle=max(0,min(.4,.4*effort)),brake=max(0,min(.8,-.5*effort)),hand_brake=remaining<-.2 and speed<.05))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start;originals={}
    for spec in cfg['cameras']:
     name=spec['name'];image=queues[name].get(timeout=30)
     while image.frame<frame:image=queues[name].get(timeout=30)
     if image.frame!=frame:raise ValueError('Original camera tick mismatch: '+name)
     encoders[name].stdin.write(image.raw_data);originals[name]=hashlib.sha256(image.raw_data).hexdigest()
    t=ego.get_transform();v=ego.get_velocity();vertices=[[p.x,p.y,p.z] for p in ego.bounding_box.get_world_vertices(t)]
    history.write(json.dumps({'frame':frame,'time_s':now,'body_vertices_m':vertices,'heading_deg':t.rotation.yaw,
     'velocity_mps':[v.x,v.y,v.z],'reverse_control':ego.get_control().reverse,'original_camera_sha256':originals})+'\n')
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
