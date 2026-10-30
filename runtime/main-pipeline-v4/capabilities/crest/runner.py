"""Recorded native crest/curve U-turn behavior comparison; sole tick owner, no database."""
import argparse,hashlib,json,math,queue,signal,subprocess,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent;INTERRUPTED=[]
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def line(f,v):f.write(json.dumps(v,allow_nan=False)+'\n');f.flush()
def xyz(v):return [float(v.x),float(v.y),float(v.z)]
def clamp(x,a,b):return max(a,min(b,x))
def static(cfg):
 from scene_model import offline_check
 assert cfg['maximum_frames']==900 and 700<=cfg['maneuver_station']<=800
 assert hashlib.sha256((ROOT/'scene.xodr').read_bytes()).hexdigest()==cfg['map_sha256']
 assert cfg['source_template']['law_id']=='NRS-484B-407'
 return offline_check()
def result_restored(out):
 return (out/'engine_scene_restored.json').exists() and json.loads((out/'engine_scene_restored.json').read_text()).get('restored') is True
def run(cfg,args):
 import carla,numpy as np
 from PIL import Image,ImageDraw
 from shapely.geometry import MultiPoint,box
 from pipeline_capture import PipelineCapture
 from native_following_capture import snapshot
 from scene_model import elevation,xy,phases
 
 from cleanup import restore
 out=Path(args.output_dir).resolve();desc=cfg['recording_description'];owned=[];streams={};encoders={};cameras={};history=[];contacts=[];capture=None;previous=None;prior_xml=None;prior_path=None;weather=None;world=None;changed=False;framefile=syncfile=None;error=None;complete=False;setup=False;reason='initialization';client=carla.Client(args.host,args.port,2);client.set_timeout(180)
 try:
  world=client.get_world();previous=world.get_settings();assert not previous.synchronous_mode
  assert not [a for a in world.get_actors() if a.type_id.startswith(('vehicle.','walker.','sensor.','controller.'))]
  prior_xml=world.get_map().to_opendrive();prior_name=world.get_map().name;weather=world.get_weather()
  paths=[x for x in client.get_available_maps() if x.rsplit('/',1)[-1]==prior_name.rsplit('/',1)[-1]];assert len(paths)==1;prior_path=paths[0]
  def fields(x):return {k:getattr(x,k) for k in dir(x) if not k.startswith('_') and isinstance(getattr(x,k),(str,bool,int,float,type(None)))}
  write(out/'previous-scene-state.json',{'map':prior_name,'map_sha256':hashlib.sha256(prior_xml.encode()).hexdigest(),'settings':fields(previous),'weather':fields(weather)});(out/'previous-world.xodr').write_text(prior_xml)
  changed=True
  world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
  settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10;world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon);mapping=world.get_map()
  
  def waypoint(s):
   w=mapping.get_waypoint_xodr(1,-1,float(s));assert w is not None;return w
  for _ in range(5):world.tick()
  survey=[]
  for station in range(450,1051,10):
   for lane in (-1,1):
    w=mapping.get_waypoint_xodr(1,lane,float(station));loc=w.transform.location;expected=xy(station,6 if lane==1 else -6)
    hits=world.cast_ray(carla.Location(x=loc.x,y=loc.y,z=loc.z+2),carla.Location(x=loc.x,y=loc.y,z=loc.z-2));raw=[{'label':str(h.label),'position_m':xyz(h.location)} for h in hits]
    assert abs(loc.z-elevation(station))<.02 and math.dist(xyz(loc)[:2],expected)<.03 and abs(w.lane_width-12)<1e-6
    assert hits and max(h.location.z for h in hits)<=loc.z+.05 and any(abs(h.location.z-loc.z)<.05 for h in hits),'Native topmost supporting surface differs'
    survey.append({'s_m':station,'lane_id':lane,'native_waypoint_m':xyz(loc),'native_rotation_deg':fields(w.transform.rotation),'all_surface_hits':raw})
  write(out/'native_hill_surface_survey.json',{'native_map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),'authored_map_sha256':cfg['map_sha256'],'surface_samples':survey,'crest_station_m':750,'native_curvature_per_m':0,'surface_tolerance_m':.05,'native_render_review_required':True})
  write(out/'native_road_profile.json',{'schema':'native-straight-road-profile-v1','map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),'survey_sha256':hashlib.sha256((out/'native_hill_surface_survey.json').read_bytes()).hexdigest(),'instrumentation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'half_road_width_m':12,'grade_patch_length_m':2,'crest_ridge_mesh_width_m':.25})
  bp=world.get_blueprint_library().find('vehicle.tesla.model3');bp.set_attribute('role_name','subject');tr=waypoint(cfg['maneuver_station']-8).transform;tr.location.z+=.35;ego=world.spawn_actor(bp,tr);owned.append(ego);ego.apply_control(carla.VehicleControl(hand_brake=True,manual_gear_shift=True,gear=1))
  bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','approaching_vehicle');tr=waypoint(500).transform;tr.location.z+=.35;other=world.spawn_actor(bp,tr);owned.append(other);other.apply_control(carla.VehicleControl(hand_brake=True,manual_gear_shift=True,gear=1))
  for _ in range(100):world.tick()
  assert ego.get_velocity().length()<.001
  b=ego.bounding_box;meta={'actor_id':ego.id,'blueprint':ego.type_id,'attributes':dict(ego.attributes),'extent_native_m':xyz(b.extent),'offset_native_m':xyz(b.location),'box_rotation_deg':fields(b.rotation),'initial_state':snapshot(ego)};write(out/'vehicle_metadata.json',meta)
  write(out/'actual_scene_identity.json',{'map_name':mapping.name,'map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),'subject_actor_id':ego.id,'other_actor_id':other.id,'synthetic_context':cfg['authored_test_context']})
  for name,parent,tr,fov in [('driver',ego,carla.Transform(carla.Location(x=-7,z=3.5),carla.Rotation(pitch=-15)),90),('other_driver',other,carla.Transform(carla.Location(x=.6,y=-.35,z=1.4)),90),('overview',None,carla.Transform(carla.Location(x=cfg['maneuver_station'],y=0,z=elevation(cfg['maneuver_station'])+36),carla.Rotation(pitch=-90)),90)]:
   bp=world.get_blueprint_library().find('sensor.camera.rgb')
   for k,v in [('image_size_x','960'),('image_size_y','540'),('fov',str(fov)),('sensor_tick','0')]:bp.set_attribute(k,v)
   camera=world.spawn_actor(bp,tr,attach_to=parent) if parent else world.spawn_actor(bp,tr);owned.append(camera);q=queue.Queue();camera.listen(q.put);cameras[name]=(camera,q)
  for actor in (ego,other):
   sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=actor);owned.append(sensor);sensor.listen(lambda e:contacts.append({'frame':e.frame,'other_actor_id':e.other_actor.id,'impulse':xyz(e.normal_impulse)}))
  for _ in range(3):world.tick()
  for camera,q in cameras.values():
   while not q.empty():q.get_nowait()
  (out/'channels').mkdir(exist_ok=True);(out/'rgb').mkdir(exist_ok=True)
  for c in desc['channels']:streams[c['name']]=(out/'channels'/(c['name']+'.jsonl')).open('x')
  framefile=(out/'video_frames.jsonl').open('x');syncfile=(out/'synchronized_motion_records.jsonl').open('x')
  actual_context={'road_grade':{'samples':[{'s_m':v['s_m'],'lane_id':v['lane_id'],'grade_ratio_from_native_pitch':math.tan(math.radians(v['native_rotation_deg']['pitch']))} for v in survey]},'road_crest_position':{'native_world_m':[*xy(750),elevation(750)],'station_m':750,'legal_near_classification':None},'road_curvature':{'native_map_arc_curvature_per_m':0,'native_heading_samples':survey,'native_xml_reference':'road.xodr'},'road_approach_directions':{'road_id':1,'lane_ids':[-1,1],'native_samples':survey},'road_geometry_reference':{'native_map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),'survey_reference':'native_hill_surface_survey.json'},'visibility_construction_context':{'implementation':'Shared actor_visibility','eye_height_m':1.4,'virtual_observers':True,'target':'Actual current native bounding-box center plus all eight vertices','distance':'Incoming driving-lane waypoint arc length to actual subject projected station','geometric_visibility_not_human_perception':True},'world_setup_fact_provenance':{'synthetic_conditions':cfg['authored_test_context'],'native_identity_reference':'actual_scene_identity.json','other_vehicle':'Actual approaching vehicle; identity/trajectory recorded. Virtual both-direction views do not imply actual approaching traffic from both directions.'}}
  write(out/'context.json',{x['name']:{'declared_unit':x['unit'],'value':actual_context[x['name']]} for x in desc['context_inputs']})
  for name,size in [('driver','960x540'),('other_driver','960x540'),('overview','960x540'),('review','1920x1140')]:
   log=(out/(name+'.encoder.log')).open('x');proc=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',size,'-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','3','-threads','2',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=log);encoders[name]=(proc,log)
  capture=PipelineCapture(client,ego,out,cfg['case_id'],required_observations=cfg['required_atoms']);capture_reader=(out/'capture/evidence.jsonl').open();start=world.get_snapshot().timestamp.elapsed_seconds;state={'integral':0.,'last_error':0.,'last_steer':0.};setup=True
  routes=phases(cfg['maneuver_station']);phase_index=0;progress=0;finished=None;hold_start=None;phase_events=[];other_integral=0.
  support=__import__('shapely.geometry',fromlist=['Polygon']).Polygon([(400,-12),(1100,-12),(1100,12),(400,12)])
  physics=ego.get_physics_control();wheelbase=(max(w.position.x for w in physics.wheels)-min(w.position.x for w in physics.wheels))/100
  max_steer=min(w.max_steer_angle for w in physics.wheels if w.max_steer_angle>0)
  assert 2.5<wheelbase<3.5 and max_steer>25 and math.degrees(math.atan(wheelbase/6))<max_steer
  write(out/'native_controller_capability.json',{'wheelbase_m':wheelbase,'front_max_steer_angle_deg':max_steer,'requested_radius_m':6,'kinematic_required_steering_deg':math.degrees(math.atan(wheelbase/6)),'actual_tracking_still_required':True,'tracking_reference':'Actor pose minus half measured wheelbase along actual body heading; actor-centre error against original path still bounded by2m','rear_reference_offset_m':-wheelbase/2})
  def control(target,phase,index):
   speed=ego.get_velocity().length();err=target-speed;state['integral']=clamp(state['integral']+err*.05,-4,4);output=.6*err+.2*state['integral'];state['last_error']=err
   route=phase['points'];gear=phase['gear'];pos=ego.get_location();yaw=math.radians(ego.get_transform().rotation.yaw);pos=carla.Location(x=pos.x-wheelbase/2*math.cos(yaw),y=pos.y-wheelbase/2*math.sin(yaw),z=pos.z);look=1.3+.35*speed;destination=route[min(len(route)-1,index+int(look/.1))];dx,dy=destination[0]-pos.x,destination[1]-pos.y
   desired=route[index];heading_error=(desired[2]-yaw+math.pi)%(2*math.pi)-math.pi;cross=-math.sin(desired[2])*(pos.x-desired[0])+math.cos(desired[2])*(pos.y-desired[1])
   curvature=(-1/6 if gear==1 else 1/6) if phase['name'] in ('forward_left','reverse_right','forward_left_exit') else 0
   angle=math.atan(wheelbase*curvature)+gear*1.2*heading_error-math.atan2(.6*cross,max(.8,speed))
   steer=clamp(angle/math.radians(max_steer),-.9,.9);steer=clamp(steer,state['last_steer']-.08,state['last_steer']+.08);state['last_steer']=steer
   if target==0 and speed<.15:return carla.VehicleControl(brake=1,hand_brake=True,reverse=gear==-1,manual_gear_shift=True,gear=gear)
   return carla.VehicleControl(throttle=clamp(output,0,.65),brake=clamp(-output,0,1),steer=steer,reverse=gear==-1,manual_gear_shift=True,gear=gear)
  for i in range(cfg['maximum_frames']):
   phase=routes[phase_index];route=phase['points'];pos=ego.get_location();actual_yaw=math.radians(ego.get_transform().rotation.yaw);pos=carla.Location(x=pos.x-wheelbase/2*math.cos(actual_yaw),y=pos.y-wheelbase/2*math.sin(actual_yaw),z=pos.z);progress=min(range(progress,min(len(route),progress+60)),key=lambda j:math.hypot(route[j][0]-pos.x,route[j][1]-pos.y));remaining=sum(math.dist(route[j][:2],route[j+1][:2]) for j in range(progress,len(route)-1));speed=ego.get_velocity().length();end_distance=math.hypot(route[-1][0]-pos.x,route[-1][1]-pos.y)
   target=min(2 if phase['gear']==1 else 1.5,math.sqrt(max(0,2*1.5*(remaining-.20))))
   if remaining<.55 or end_distance<.55:
    target=0
    if speed<.08:
     hold_start=i if hold_start is None else hold_start
     if i-hold_start>=20:
      if phase_index<len(routes)-1:
       phase_events.append({'completed_phase':phase['name'],'frame_before_transition':world.get_snapshot().frame,'observed_speed_mps':speed});phase_index+=1;progress=0;hold_start=None;state={'integral':0.,'last_error':0.,'last_steer':0.}
      else:finished=finished if finished is not None else i
   inputs={'source_frame':world.get_snapshot().frame,'path_progress_index':progress,'requested_speed_mps':target,'remaining_requested_path_m':remaining,'requested_path_phase':phase['name'],'requested_gear':phase['gear'],'phase_index':phase_index}
   other_speed=other.get_velocity().length();other_error=2-other_speed;other_integral=clamp(other_integral+other_error*.05,-4,4);other_output=.6*other_error+.2*other_integral;other_yaw=math.radians(other.get_transform().rotation.yaw);other_steer=clamp(-.4*(other.get_location().y-6)-1.2*other_yaw,-.4,.4)
   responses=client.apply_batch_sync([carla.command.ApplyVehicleControl(ego.id,control(target,phase,min(progress,len(phase['points'])-1))),carla.command.ApplyVehicleControl(other.id,carla.VehicleControl(throttle=clamp(other_output,0,.6),brake=clamp(-other_output,0,1),steer=other_steer,manual_gear_shift=True,gear=1))],False);assert not any(r.has_error() for r in responses);frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
   packet={'frame':frame,'time_s':now,'ego':snapshot(ego),'other':snapshot(other),'controller_inputs':inputs,'contacts':list(contacts),'path_tracking_error_m':min(math.hypot(p[0]-ego.get_location().x,p[1]-ego.get_location().y) for p in phase['points'])}
   body=MultiPoint([(p[0],p[1]) for p in packet['ego']['body_vertices_native_m']]).convex_hull;other_body=MultiPoint([(p[0],p[1]) for p in packet['other']['body_vertices_native_m']]).convex_hull;packet['whole_body_inside_roadway']=support.covers(body) and support.covers(other_body);packet['Euclidean_polygon_separation_m']=body.distance(other_body)
   current_station=mapping.get_waypoint(ego.get_location()).s;before=mapping.get_waypoint_xodr(1,-1,current_station-.25);after=mapping.get_waypoint_xodr(1,-1,current_station+.25);profile={'frame':frame,'time_s':now,'s_m':current_station,'native_z_before_after_m':[before.transform.location.z,after.transform.location.z],'map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()}
   capture.capture(frame,now,extra={'native_road_profile':profile,'crest_reversal_native':packet,'scene_actor_inventory':[{'id':a.id,'type':a.type_id} for a in world.get_actors()]});event=json.loads(capture_reader.readline());packet['visibility']=event['visibility'];packet['native_road_projection']=event['world']['road_projection'];line(syncfile,{'time_s':now,'value':{'frame':frame,'ego':packet['ego'],'other':packet['other']}})
   images={}
   for name,(camera,q) in cameras.items():
    im=q.get(timeout=30)
    while im.frame<frame:im=q.get(timeout=30)
    assert im.frame==frame;images[name]=Image.fromarray(np.frombuffer(im.raw_data,dtype=np.uint8).reshape(540,960,4)[:,:,:3][:,:,::-1])
   packet['camera_frame']=frame;history.append(packet)
   for c in desc['channels']:
    value=packet['ego']['speed_mps'] if c['name']=='ego_speed' else packet['native_road_projection']['s_m']-750 if c['name']=='maneuver_position_relative_to_crest' else packet
    line(streams[c['name']],{'time_s':now,'value':value})
   line(framefile,{'video_frame':i,'carla_frame':frame,'time_s':now})
   canvas=Image.new('RGB',(1920,1140),'#151515');canvas.paste(images['driver'],(0,60));canvas.paste(images['overview'],(960,60));canvas.paste(images['other_driver'],(0,600));draw=ImageDraw.Draw(canvas);draw.text((12,8),cfg['case_id']+' | original t %.2fs | actual speed %.3fm/s'%(now,packet['ego']['speed_mps']),fill='white');draw.text((12,28),'Native RGB: subject chase / crest overview / actual approaching-driver RGB | forward-reverse-forward; crest judgment unresolved',fill='white');draw.text((980,620),'Both incoming-lane body ray histories retained; nine samples do not establish legal recognizability',fill='white')
   if i in (0,50,100,150,200,250,300,400,499):
    for name,im in images.items():im.save(out/'rgb'/('%s-%06d.png'%(name,i)))
   for name,im in dict(images,review=canvas).items():encoders[name][0].stdin.write(im.tobytes())
   if not packet['whole_body_inside_roadway']:reason='roadway_departure';break
   if contacts:reason='collision';break
   if any(abs(actor.get_transform().rotation.roll)>30 or abs(actor.get_transform().rotation.pitch)>30 for actor in (ego,)):reason='loss_of_control';break
   if INTERRUPTED:reason='interrupted';break
  else:complete=finished is not None and phase_index==len(routes)-1 and ego.get_velocity().length()<.1 and abs(abs(ego.get_transform().rotation.yaw)-180)<15;reason='completed_three_point_reversal_and_opposite_departure' if complete else 'incomplete_path'
  capture_reader.close()
  capture.close(confirmed=complete);capture=None
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
   try:write(out/'engine_scene_restored.json',restore(carla,client,world,owned,previous,weather,prior_path,prior_xml,args.host,args.port,out))
   except BaseException as exc:
    if error is None:error={'type':'restoration_failure','message':str(exc),'traceback':traceback.format_exc()}
  matched=complete and error is None and len(history)==cfg['maximum_frames'] and max([h['path_tracking_error_m'] for h in history] or [1e9])<2 and bool(result_restored(out))
  result={'status':'draft','cell_id':cfg['cell_id'],'actor':'motor_vehicle_driver','case_id':cfg['case_id'],'setup_confirmed':setup,'behavior_attempted':any(h['ego']['speed_mps']>.001 for h in history),'maneuver_completed':complete,'termination_reason':reason,'physical_failure_flags':{'collision':bool(contacts),'loss_of_control':reason=='loss_of_control','roadway_departure':reason=='roadway_departure'},'target_checks':[{'target':'commanded_turn_path','requested':cfg['variable_assignments']['commanded_turn_path']['value'],'measured':{'path_progress_index':progress if setup else None,'maximum_path_error_m':max([h['path_tracking_error_m'] for h in history] or [0]),'frames':len(history)},'method':'Actual native forward-reverse-forward physics path, both eight-vertex actor footprints, original20Hz two-direction body visibility; no legal judgment or requested state substitution','tolerance':{'path_tracking_m':2},'matched':matched,'physical_cause_confirmed':setup,'cause_evidence':['native_hill_surface_survey.json','channels/native_maneuver_state.jsonl','overview.mkv']}],'measured_values':{'frames':len(history),'duration_s':len(history)/20},'requested_assignments':cfg['variable_assignments'],'trace_reference':'trace.jsonl' if history else None,'video_references':videos,'video_frame_map_reference':'video_frames.jsonl' if history else None,'recording_description':desc,'recording_evidence':[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'} for c in desc['channels'] if c['name'] in streams]+[{'name':x['name'],'unit':x['unit'],'reference':'context.json#/'+x['name']} for x in desc['context_inputs'] if (out/'context.json').exists()],'realized_observables':{},'recording_complete':bool(complete and len(videos)==4 and error is None),'error':error,'limitations':desc.get('limitations',[])}
  result['requested_variable_assignments']={k:v for k,v in cfg['variable_assignments'].items() if v['kind'] in ('controller','world_setup')}
  result['input_revision']=cfg['input_revision'];result['phase_events']=phase_events if setup else [];result['restoration']=json.loads((out/'engine_scene_restored.json').read_text()) if (out/'engine_scene_restored.json').exists() else {'restored':False}
  reverse_sample=next((h for h in history if h['controller_inputs']['requested_gear']==-1),None)
  if reverse_sample:
   m=cfg['case']['sweep_measurements'][0]['measurement'];result['realized_observables']['maneuver_position_relative_to_crest']={'value':reverse_sample['native_road_projection']['s_m']-750,'unit':'m','method':m['method'],'time_window':m['time_window'],'statistic':'first','sample_window_s':[reverse_sample['time_s'],reverse_sample['time_s']],'reference':'channels/maneuver_position_relative_to_crest.jsonl'}
  write(out/'result.json',result)
 return 0 if matched else 2
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output-dir',default=str(ROOT));p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=23000);p.add_argument('--check',action='store_true');a=p.parse_args();cfg=json.loads((ROOT/'config.json').read_text())
 if a.check:print(json.dumps(static(cfg)))
 else:
  for s in (signal.SIGINT,signal.SIGTERM):signal.signal(s,lambda n,f:INTERRUPTED.append(n))
  sys.exit(run(cfg,a))
