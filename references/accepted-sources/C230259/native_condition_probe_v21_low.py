"""Explicit non-ego-driving native feasibility measurements for one next comparison."""
import argparse,ast,copy,fcntl,json,math,queue,sys,traceback,xml.etree.ElementTree as ET
from pathlib import Path
O=Path(__file__).resolve().parent;P=O.parents[5];C=O/'common-condition-v21-low';sys.path[:0]=[str(C),str(P/'scenario_pipeline'),str(P/'scripts'),str(P/'third_party/carla_scene_graphs')]
import carla,numpy as np
from PIL import Image
from batch_pipeline.engine_worker import server_identity,identity_key
from environment_capture import calibrate,surface_receipt,fields,sha,write,xyz,get_image
from native_following_capture import snapshot
from cleanup import restore
p=argparse.ArgumentParser();p.add_argument('--comparison',choices=['highway_width','precipitation','visibility','surface_friction','supported_traffic_categories'],required=True);p.add_argument('--value',type=float,default=0);p.add_argument('--pedestrians',type=int,default=0);p.add_argument('--bicycles',type=int,default=0);p.add_argument('--directory',type=Path,required=True);p.add_argument('--engine-root',type=Path,required=True);args=p.parse_args()
assert (O/'publication-receipt-v2.json').exists(),'Finish and publish first speed comparison before starting another comparison'
assert O in args.directory.resolve().parents and O in args.engine_root.resolve().parents
root=args.directory.resolve();root.mkdir(parents=True,exist_ok=False);identity=server_identity(22100);launcher=json.loads((args.engine_root/'launcher.json').read_text());assert launcher['ready'] and launcher['pid']==identity['pid']
weather_values=json.loads((O/'setup-probe-v4/environment_calibration.json').read_text())['weather'];native_width=10.;friction=None
xml=ET.fromstring((C/'scene.xodr').read_text())
if args.comparison=='highway_width':
 native_width=args.value;assert 8<=native_width<=12;shoulder=(native_width-7)/2
 for width in xml.findall(".//lane[@type='shoulder']/width"):width.set('a',str(shoulder))
if args.comparison=='precipitation':weather_values.update(precipitation=args.value,cloudiness=60.,wetness=0.,precipitation_deposits=0.)
if args.comparison=='visibility':weather_values['fog_density']=args.value
if args.comparison=='surface_friction':friction=args.value
(root/'authored_road.xodr').write_text(ET.tostring(xml,encoding='unicode'));write(root/'request.json',{'comparison':args.comparison,'value':args.value,'pedestrians':args.pedestrians,'bicycles':args.bicycles,'weather':weather_values,'native_highway_width_m':native_width,'friction_trigger_parameter':friction,'actor':'motor_vehicle_driver','ego_driving_episode':False,'moving_participant_capability_calibration':args.comparison=='supported_traffic_categories','instrument_source_sha256':sha(C/'environment_capture.py')})
owned=[];client=carla.Client('127.0.0.1',22100);client.set_timeout(180);changed=False
with (P/'runs/scenario_pipeline/state/engines'/(identity_key(identity)+'.lock')).open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 world=client.get_world();previous=world.get_settings();assert not previous.synchronous_mode;assert not [a for a in world.get_actors() if a.type_id.startswith(('vehicle.','walker.','sensor.'))]
 previous_weather=world.get_weather();prior_xml=world.get_map().to_opendrive();prior_name=world.get_map().name;prior_path=next(x for x in client.get_available_maps() if x.rsplit('/',1)[-1]==prior_name.rsplit('/',1)[-1])
 write(root/'prior-scene.json',{'map':prior_name,'map_xml_sha256':__import__('hashlib').sha256(prior_xml.encode()).hexdigest(),'settings':fields(previous),'weather':fields(previous_weather)})
 try:
  changed=True;world=client.generate_opendrive_world((root/'authored_road.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False));settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10;world.apply_settings(settings)
  weather=carla.WeatherParameters()
  for key,value in weather_values.items():setattr(weather,key,value)
  world.set_weather(weather);mapping=world.get_map();(root/'road.xodr').write_text(mapping.to_opendrive());survey=[]
  for station in (70,300,600,900,1100,1300,1730):
   widths=[]
   for lane in (-2,-1,1,2):
    wp=mapping.get_waypoint_xodr(1,lane,station);assert wp;widths.append(wp.lane_width);loc=wp.transform.location;hits=world.cast_ray(carla.Location(x=loc.x,y=loc.y,z=2),carla.Location(x=loc.x,y=loc.y,z=-2));assert any(abs(h.location.z)<.05 for h in hits)
    survey.append({'station_m':station,'lane':lane,'native_width_m':wp.lane_width,'native_position_m':xyz(loc),'surface_hits':[{'label':str(h.label),'position_m':xyz(h.location)} for h in hits]})
   assert abs(sum(widths)-native_width)<1e-5
  write(root/'native-surface-survey.json',survey)
  for name,station,lane in [('vehicle.tesla.model3',300,-1),('vehicle.lincoln.mkz_2020',1100,1)]:
   bp=world.get_blueprint_library().find(name);tr=mapping.get_waypoint_xodr(1,lane,station).transform;tr.location.z+=.35;a=world.spawn_actor(bp,tr);owned.append(a);a.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  ego,other=owned[:];extras=[];trigger=None
  if friction is not None:
   bp=world.get_blueprint_library().find('static.trigger.friction')
   for k,v in [('friction',str(friction)),('extent_x','90000'),('extent_y','1000'),('extent_z','200')]:bp.set_attribute(k,v)
   trigger=world.spawn_actor(bp,carla.Transform(carla.Location(x=900,z=0)));owned.append(trigger)
  if args.comparison=='supported_traffic_categories':
   for kind,count in [('pedestrian',args.pedestrians),('bicycle',args.bicycles)]:
    assert count in (0,1)
    for i in range(count):
     bp=world.get_blueprint_library().find('walker.pedestrian.0001' if kind=='pedestrian' else 'vehicle.gazelle.omafiets');tr=carla.Transform(carla.Location(x=500 if kind=='pedestrian' else 700,y=4.25,z=1.2 if kind=='pedestrian' else .35));a=world.spawn_actor(bp,tr);owned.append(a);extras.append(a)
     if kind=='pedestrian':a.apply_control(carla.WalkerControl(speed=0))
     else:a.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for _ in range(50):world.tick()
  wheel_friction=[w.tire_friction for w in ego.get_physics_control().wheels]
  if friction is not None:assert all(abs(v-friction)<1e-5 for v in wheel_friction),('Native trigger did not update wheel friction',wheel_friction)
  write(root/'native-capabilities.json',{'ego':snapshot(ego),'other':snapshot(other),'extra_traffic':[snapshot(a) for a in extras],'ego_physics':fields(ego.get_physics_control()),'ego_wheels':[fields(w) for w in ego.get_physics_control().wheels],'friction_trigger':None if trigger is None else {'id':trigger.id,'attributes':dict(trigger.attributes),'position_m':xyz(trigger.get_location())},'native_world_api_names':[name for name in dir(world) if any(k in name for k in ('mesh','material','object'))]})
  if extras:
   camera_queues={}
   for a in extras:
    bp=world.get_blueprint_library().find('sensor.camera.rgb');bp.set_attribute('image_size_x','960');bp.set_attribute('image_size_y','540');bp.set_attribute('fov','90');cam=world.spawn_actor(bp,carla.Transform(carla.Location(x=-5,z=3),carla.Rotation(pitch=-20)),attach_to=a);owned.append(cam);q=queue.Queue();cam.listen(q.put);camera_queues[a.id]=(cam,q);(root/('traffic-rgb-'+str(a.id))).mkdir()
   for _ in range(3):world.tick()
   for cam,q in camera_queues.values():
    while not q.empty():q.get_nowait()
   start=world.get_snapshot().timestamp.elapsed_seconds
   states={x.id:0. for x in extras};node=copy.deepcopy(next(n for n in ast.walk(ast.parse((C/'runner.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='control'));scope={'carla':carla,'math':math,'clamp':lambda x,a,b:max(a,min(b,x)),'states':states,'mapping':mapping};exec(compile(ast.Module(body=[node],type_ignores=[]),str(C/'runner.py'),'exec'),scope);controller=scope['control']
   with (root/'traffic-capability-motion.jsonl').open('x') as stream:
    for i in range(400):
     for a in extras:
      if a.type_id.startswith('walker.'):a.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=1),speed=1.4))
      else:
       bicycle_control=controller(a,1,-2);bicycle_control.manual_gear_shift=True;bicycle_control.gear=1;a.apply_control(bicycle_control)
     frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start;record={'frame':frame,'time_s':now,'ego':snapshot(ego),'participants':[snapshot(a) for a in extras],'camera_frames':{}}
     assert record['ego']['speed_mps']<.05,'No ego driving episode permitted in setup probe'
     for aid,(cam,q) in camera_queues.items():
      im=get_image(q,frame);image=Image.fromarray(np.frombuffer(im.raw_data,dtype=np.uint8).reshape(540,960,4)[:,:,:3][:,:,::-1]);path=root/('traffic-rgb-'+str(aid))/('%06d.png'%i);image.save(path);record['camera_frames'][str(aid)]={'frame':im.frame,'path':str(path.relative_to(root)),'sha256':sha(path)}
     stream.write(json.dumps(record)+'\n')
   for cam,q in camera_queues.values():cam.stop();cam.destroy();owned.remove(cam)
   observations=[json.loads(x) for x in (root/'traffic-capability-motion.jsonl').read_text().splitlines()]
   for index,a in enumerate(extras):
    distance=math.dist(observations[0]['participants'][index]['position_m'],observations[-1]['participants'][index]['position_m']);assert distance>.5,('Native traffic actor did not travel',a.type_id,distance)
   write(root/'traffic-capability-outcome.json',{'passed':True,'frames':400,'ego_driving_episode':False,'participants':[{'type':a.type_id,'actual_end':snapshot(a)} for a in extras],'scope':'Explicit20second closed-loop native pedestrian/bicycle capability calibration; not an accepted selected ego case'})
  cal=calibrate(world,other,root,owned);surface_receipt(world,mapping,root,root/'authored_road.xodr',[P/'carla/CarlaUE4/Content/Carla/Maps/OpenDriveMap.umap',P/'carla/CarlaUE4/Content/Carla/Maps/OpenDriveMap.uexp'])
  write(root/'setup-checks.json',{'passed':True,'comparison':args.comparison,'native_highway_width_m':native_width,'actual_weather':fields(world.get_weather()),'ego_native_wheel_friction':wheel_friction,'traffic_counts':{'pedestrian':args.pedestrians,'bicycle':args.bicycles},'visibility':{'value_m':cal['visibility_m'],'kind':cal['distance_kind']},'server_identity':identity,'ego_driving_episode':False,'graphics_quality':[v.split('=',1)[1] for v in launcher['argv'] if v.startswith('-quality-level=')][0],'owned_launcher_receipt_sha256':sha(args.engine_root/'launcher.json')})
 except BaseException as exc:
  write(root/'failure.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()});raise
 finally:
  if changed:write(root/'restoration.json',restore(carla,client,world,owned,previous,previous_weather,prior_path,prior_xml,'127.0.0.1',22100,root))
print(json.dumps({'directory':str(root),'native_probe_passed':True,'ego_driving_episode':False}),flush=True)
