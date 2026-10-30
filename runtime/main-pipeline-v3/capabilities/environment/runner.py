"""One original45s physics episode, measured conditions and complete native capture."""
import argparse,hashlib,json,math,queue,signal,subprocess,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent;INTERRUPTED=[]
from environment_capture import calibrate,surface_receipt,fields,write,sha,xyz,get_image
from scene_model import offline_check

def line(f,v):f.write(json.dumps(v,allow_nan=False)+'\n');f.flush()
def clamp(x,a,b):return max(a,min(b,x))
def static(cfg):
 assert cfg['maximum_frames']==900 and cfg['commanded_speed_mps'] in (3,5,7,9,11,13,15)
 assert sha(ROOT/'scene.xodr')==cfg['map_sha256'];return offline_check()
def run(cfg,args):
 import carla,numpy as np
 from PIL import Image,ImageDraw
 from shapely.geometry import MultiPoint,box
 from pipeline_capture import PipelineCapture
 from native_following_capture import snapshot
 from cleanup import restore
 out=Path(args.output_dir);owned=[];streams={};cameras={};encoders={};history=[];contacts=[];capture=None;previous=None;prior_xml=None;prior_path=None;prior_weather=None;world=None;changed=False;framefile=syncfile=None;error=None;complete=False;setup=False;reason='initialization';client=carla.Client(args.host,args.port,2);client.set_timeout(180)
 try:
  world=client.get_world();previous=world.get_settings();assert not previous.synchronous_mode
  assert not [a for a in world.get_actors() if a.type_id.startswith(('vehicle.','walker.','sensor.','controller.'))]
  prior_xml=world.get_map().to_opendrive();prior_name=world.get_map().name;prior_weather=world.get_weather();prior_path=next(x for x in client.get_available_maps() if x.rsplit('/',1)[-1]==prior_name.rsplit('/',1)[-1])
  write(out/'previous-scene-state.json',{'map':prior_name,'settings':fields(previous),'weather':fields(prior_weather)});(out/'previous-world.xodr').write_text(prior_xml)
  changed=True;world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
  settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10;world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon);mapping=world.get_map();(out/'road.xodr').write_text(mapping.to_opendrive());actual_weather=fields(world.get_weather())
  survey=[]
  for s in (70,300,600,900,1100,1300,1730):
   for lane in (-2,-1,1,2):
    wp=mapping.get_waypoint_xodr(1,lane,s);assert wp;loc=wp.transform.location
    hits=world.cast_ray(carla.Location(x=loc.x,y=loc.y,z=2),carla.Location(x=loc.x,y=loc.y,z=-2));assert hits and any(abs(h.location.z)<.05 for h in hits)
    survey.append({'s_m':s,'lane_id':lane,'position_m':xyz(loc),'width_m':wp.lane_width,'hits':[{'label':str(h.label),'position_m':xyz(h.location)} for h in hits]})
  write(out/'native_surface_survey.json',survey)
  for name,s,lane in [('vehicle.tesla.model3',300,-1),('vehicle.lincoln.mkz_2020',1100,1)]:
   bp=world.get_blueprint_library().find(name);bp.set_attribute('role_name','subject' if lane==-1 else 'oncoming_vehicle');tr=mapping.get_waypoint_xodr(1,lane,s).transform;tr.location.z+=.35;actor=world.spawn_actor(bp,tr);owned.append(actor);actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  ego,other=owned[:]
  for _ in range(50):world.tick()
  calibration=calibrate(world,other,out,owned);assert actual_weather==calibration['weather']
  surface_receipt(world,mapping,out,ROOT/'scene.xodr',[Path(p) for p in cfg['surface_asset_paths']]);calhash=sha(out/'environment_calibration.json');surfhash=sha(out/'surface_provenance.json')
  write(out/'vehicle_metadata.json',{a.type_id:{'id':a.id,'initial_state':snapshot(a),'physics':fields(a.get_physics_control()),'wheels':[fields(w) for w in a.get_physics_control().wheels]} for a in (ego,other)})
  write(out/'actual_scene_identity.json',{'map_name':mapping.name,'map_sha256':sha(out/'road.xodr'),'subject_actor_id':ego.id,'other_actor_id':other.id,'synthetic_context':cfg['authored_test_context']})
  for name,parent,tr in [('driver',ego,carla.Transform(carla.Location(x=-7,z=3.5),carla.Rotation(pitch=-15))),('other_driver',other,carla.Transform(carla.Location(x=.6,y=-.35,z=1.4))),('overview',ego,carla.Transform(carla.Location(x=-2,z=18),carla.Rotation(pitch=-80)))]:
   bp=world.get_blueprint_library().find('sensor.camera.rgb')
   for k,v in [('image_size_x','960'),('image_size_y','540'),('fov','90'),('sensor_tick','0')]:bp.set_attribute(k,v)
   camera=world.spawn_actor(bp,tr,attach_to=parent);owned.append(camera);q=queue.Queue();camera.listen(q.put);cameras[name]=(camera,q)
  for a in (ego,other):
   sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=a);owned.append(sensor);sensor.listen(lambda e:contacts.append({'frame':e.frame,'other_actor_id':e.other_actor.id,'impulse':xyz(e.normal_impulse)}))
  for _ in range(3):world.tick()
  for camera,q in cameras.values():
   while not q.empty():q.get_nowait()
  desc=cfg['recording_description'];(out/'channels').mkdir();(out/'rgb').mkdir()
  for c in desc['channels']:streams[c['name']]=(out/'channels'/(c['name']+'.jsonl')).open('x')
  framefile=(out/'video_frames.jsonl').open('x');syncfile=(out/'synchronized_motion_records.jsonl').open('x')
  context={x['name']:{'declared_unit':x['unit'],'value':{'source':'Exact original setup/metadata/calibration and configuration','native_scene':'actual_scene_identity.json','surface':'surface_provenance.json','environment':'environment_calibration.json','vehicle_physics':'vehicle_metadata.json','road_geometry':'road.xodr','survey':'native_surface_survey.json','measurement_reference':{'dt_s':.05,'Core_t':'round(original_time_s*1000)','world_axes':'native CARLA XYZ; Core reflects y','station':'native road1 station in metres'},'synthetic_context':cfg['authored_test_context']}} for x in desc['context_inputs']};write(out/'context.json',context)
  for name,size in [('driver','960x540'),('other_driver','960x540'),('overview','960x540'),('review','1920x1140')]:
   log=(out/(name+'.encoder.log')).open('x');proc=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',size,'-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','3','-threads','2',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=log);encoders[name]=(proc,log)
  capture=PipelineCapture(client,ego,out,cfg['case_id'],visibility=True,required_observations=cfg['required_atoms']);reader=(out/'capture/evidence.jsonl').open();start=world.get_snapshot().timestamp.elapsed_seconds;states={ego.id:0.,other.id:0.};setup=True
  def control(a,target,lane):
   speed=a.get_velocity().length();err=target-speed;old=states[a.id];trial=clamp(old+err*.05,-3,3);output=.6*err+.15*trial
   if not (output>.75 and err>0) and not (output<0 and err<0):states[a.id]=trial
   output=.6*err+.15*states[a.id];wp=mapping.get_waypoint_xodr(1,lane,clamp(a.get_location().x,1,1799));desired=math.radians(wp.transform.rotation.yaw);yaw=math.radians(a.get_transform().rotation.yaw);he=(desired-yaw+math.pi)%(2*math.pi)-math.pi;cross=math.cos(desired)*(a.get_location().y-wp.transform.location.y)
   steer=clamp(-.35*cross+1.2*he,-.5,.5)
   if target==0:return carla.VehicleControl(brake=.7,hand_brake=speed<.05,steer=steer)
   return carla.VehicleControl(throttle=clamp(output,0,.75),brake=clamp(-output,0,1),steer=steer)
  for i in range(cfg['maximum_frames']):
   elapsed=i*.05;phase='stationary_initialization' if elapsed<2 else 'acceleration_and_steady' if elapsed<25 else 'braking_and_stopped_outcome';target=cfg['commanded_speed_mps'] if 2<=elapsed<25 else 0
   before={'frame':world.get_snapshot().frame,'time_s':elapsed,'ego':snapshot(ego),'other':snapshot(other)}
   controls=[carla.command.ApplyVehicleControl(ego.id,control(ego,target,-1)),carla.command.ApplyVehicleControl(other.id,control(other,7,1))];assert not any(r.has_error() for r in client.apply_batch_sync(controls,False));frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
   observed_weather=fields(world.get_weather());assert observed_weather==calibration['weather'],'Atmosphere changed since calibration'
   env={'frame':frame,'time_s':now,'weather':observed_weather,'visibility_m':calibration['visibility_m'],'ice_or_snow':False,'calibration_sha256':calhash,'surface_sha256':surfhash}
   packet={'frame':frame,'time_s':now,'ego':snapshot(ego),'other':snapshot(other),'phase':phase,'command_time_s':elapsed,'commanded_speed_mps':target,'pre_control_state':before,'environment_measurements':env,'contacts':list(contacts)}
   bodies=[MultiPoint([(v[0],v[1]) for v in packet[k]['body_vertices_native_m']]).convex_hull for k in ('ego','other')];packet['whole_body_inside_roadway']=all(box(0,-3.5,1800,3.5).covers(b) for b in bodies);packet['Euclidean_polygon_separation_m']=bodies[0].distance(bodies[1]);packet['native_component_gap_m']=None
   capture.capture(frame,now,extra={'speed_comparison_native':packet,'environment_measurements':env,'scene_actor_inventory':[{'id':a.id,'type':a.type_id} for a in world.get_actors()]});event=json.loads(reader.readline());packet['geometric_sight_distance']=event['visibility'];packet['native_road_projection']=event['world']['road_projection'];history.append(packet);line(syncfile,{'time_s':now,'value':packet})
   for c in desc['channels']:
    value=packet['ego']['speed_mps'] if c['name']=='ego_speed' else packet
    line(streams[c['name']],{'time_s':now,'value':value})
   images={}
   for name,(camera,q) in cameras.items():
    im=get_image(q,frame);images[name]=Image.fromarray(np.frombuffer(im.raw_data,dtype=np.uint8).reshape(540,960,4)[:,:,:3][:,:,::-1])
   line(framefile,{'video_frame':i,'carla_frame':frame,'time_s':now})
   canvas=Image.new('RGB',(1920,1140),'#151515');canvas.paste(images['driver'],(0,60));canvas.paste(images['overview'],(960,60));canvas.paste(images['other_driver'],(0,600));draw=ImageDraw.Draw(canvas);draw.text((12,8),cfg['case_id']+' | original t %.2fs | observed speed %.3fm/s | command %.1f'%(now,packet['ego']['speed_mps'],target),fill='white');draw.text((12,28),'Native RGB: ego chase / moving overview / actual oncoming driver | full45s | reasonable/proper judgment unresolved',fill='white');draw.text((980,620),'Highway10m / roadway7m / lanes3.5m; environmental contrast range and geometric sight distance retained separately',fill='white')
   if i in (0,40,100,300,480,500,550,700,899):
    for name,im in images.items():im.save(out/'rgb'/('%s-%06d.png'%(name,i)))
   for name,im in dict(images,review=canvas).items():encoders[name][0].stdin.write(im.tobytes())
   if contacts:reason='collision';break
   if not packet['whole_body_inside_roadway']:reason='roadway_departure';break
   if abs(ego.get_transform().rotation.roll)>30:reason='loss_of_control';break
   if INTERRUPTED:reason='interrupted';break
  else:complete=ego.get_velocity().length()<.05;reason='completed_acceleration_steady_braking_stopped_episode' if complete else 'failed_to_stop'
  reader.close();capture.close(confirmed=complete);capture=None
 except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()};reason='construction_or_capture_failure'
 finally:
  if capture:
   try:capture.close(confirmed=False)
   except Exception:pass
  for f in list(streams.values())+[framefile,syncfile]:
   if f:f.close()
  videos=[]
  for name,(proc,log) in encoders.items():
   try:proc.stdin.close();assert proc.wait(timeout=180)==0;videos.append(name+'.mkv')
   except Exception as exc:
    if error is None:error={'type':'encoding_failure','message':str(exc)}
   log.close()
  if changed and prior_xml is not None:
   try:write(out/'engine_scene_restored.json',restore(carla,client,world,owned,previous,prior_weather,prior_path,prior_xml,args.host,args.port,out))
   except BaseException as exc:
    if error is None:error={'type':'restoration_failure','message':str(exc),'traceback':traceback.format_exc()}
  steady=[h for h in history if 15<=h['time_s']<=24];steady_match=len(steady)>=100 and all(abs(h['ego']['speed_mps']-cfg['commanded_speed_mps'])<=.5 for h in steady)
  braking=next((h for h in history if h['phase']=='braking_and_stopped_outcome'),None);stopped=next((h for h in history if braking and h['time_s']>=braking['time_s'] and h['ego']['speed_mps']<=.05),None)
  stopping=None
  if braking and stopped:
   startp=braking['pre_control_state']['ego']['position_m'];endp=stopped['ego']['position_m'];stopping={'command_time_s':braking['command_time_s'],'first_applied_control_frame':braking['frame'],'first_applied_control_time_s':braking['time_s'],'start_reference':'Original pre-control native actor position, before braking tick','start_position_m':startp,'cessation_frame':stopped['frame'],'cessation_time_s':stopped['time_s'],'cessation_speed_mps':stopped['ego']['speed_mps'],'end_position_m':endp,'displacement_m':math.dist(startp,endp),'uncertainty':'50ms endpoint bracket; cessation <=0.05m/s is an engineering convention, no legal stopping threshold. Endpoint positions retained separately from integrated path.','time_history_reference':'synchronized_motion_records.jsonl'};write(out/'observed_stopping_event.json',stopping)
  restored=(out/'engine_scene_restored.json').exists() and json.loads((out/'engine_scene_restored.json').read_text()).get('restored')
  matched=complete and len(history)==900 and steady_match and stopping is not None and error is None and restored
  checks=[{'target':'commanded_speed','requested':cfg['commanded_speed_mps'],'measured':{'steady_min_mps':min([h['ego']['speed_mps'] for h in steady] or [0]),'steady_max_mps':max([h['ego']['speed_mps'] for h in steady] or [0]),'sample_count':len(steady),'window_s':[15,24]},'method':'Actual same-frame native velocity norm, every sample15..24s','tolerance':{'speed_mps':.5,'minimum_interval_s':5},'matched':bool(steady_match),'physical_cause_confirmed':setup,'cause_evidence':['synchronized_motion_records.jsonl']},{'target':'complete_episode','requested':900,'measured':len(history),'method':'Full original45second20Hz acceleration/steady/braking/stopped episode','tolerance':0,'matched':bool(matched),'physical_cause_confirmed':setup,'cause_evidence':['video_frames.jsonl','observed_stopping_event.json']}]
  result={'status':'draft','cell_id':'C230259','actor':'motor_vehicle_driver','case_id':cfg['case_id'],'input_revision':cfg['input_revision'],'setup_confirmed':setup,'behavior_attempted':any(h['ego']['speed_mps']>.01 for h in history),'maneuver_completed':complete,'termination_reason':reason,'physical_failure_flags':{'collision':bool(contacts),'roadway_departure':reason=='roadway_departure','loss_of_control':reason=='loss_of_control'},'target_checks':checks,'measured_values':{'frames':len(history),'duration_s':len(history)/20,'observed_stopping_event':stopping},'requested_assignments':cfg['variable_assignments'],'requested_variable_assignments':{k:v for k,v in cfg['variable_assignments'].items() if v['kind'] in ('world_setup','controller')},'trace_reference':'trace.jsonl' if history else None,'video_references':videos,'video_frame_map_reference':'video_frames.jsonl' if history else None,'recording_description':cfg['recording_description'],'recording_evidence':[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'} for c in cfg['recording_description']['channels'] if c['name'] in streams]+[{'name':x['name'],'unit':x['unit'],'reference':'context.json#/'+x['name']} for x in cfg['recording_description']['context_inputs'] if (out/'context.json').exists()],'realized_observables':{},'recording_complete':bool(complete and len(videos)==4 and error is None),'restoration':{'restored':bool(restored)},'error':error,'limitations':cfg['recording_description']['limitations']}
  if steady:
   m=cfg['case']['sweep_measurements'][0]['measurement'];result['realized_observables']['ego_speed']={'value':sum(h['ego']['speed_mps'] for h in steady)/len(steady),'unit':'m/s','method':m['method'],'time_window':m['time_window'],'statistic':'mean','sample_window_s':[steady[0]['time_s'],steady[-1]['time_s']],'reference':'channels/ego_speed.jsonl'}
  write(out/'result.json',result)
 return 0 if matched else 2
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output-dir',default=str(ROOT));p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=22100);p.add_argument('--check',action='store_true');args=p.parse_args();cfg=json.loads((ROOT/'config.json').read_text())
 if args.check:print(json.dumps(static(cfg)))
 else:
  for s in (signal.SIGINT,signal.SIGTERM):signal.signal(s,lambda n,f:INTERRUPTED.append(n))
  sys.exit(run(cfg,args))
