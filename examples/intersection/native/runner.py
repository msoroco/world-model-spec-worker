"""One retained original stop257 motion research episode, never delivery.

Native controls drive ordinary vehicles; no teleportation, speed forcing, legal
hazard thresholds, or replay for camera/graph capture. Full original history stays.
"""
import argparse,json,math,queue,shutil,subprocess,sys,traceback,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def write(path,value):
 with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def state(actor):
 from original_observations import actor_state
 v=actor_state(actor);t=actor.get_transform();c=actor.get_control();b=actor.bounding_box;acc=actor.get_acceleration();v['native_acceleration_mps2']=[acc.x,acc.y,acc.z]
 v.update(applied_control={k:getattr(c,k) for k in ['throttle','brake','steer','hand_brake','reverse','manual_gear_shift','gear']},native_transform_matrix=t.get_matrix(),body_local_vertices_m=[[p.x,p.y,p.z] for p in b.get_local_vertices()],native_bbox_extent_m=[b.extent.x,b.extent.y,b.extent.z],native_bbox_offset_m=[b.location.x,b.location.y,b.location.z],queried_lights=int(actor.get_light_state()))
 return v

def run(args):
 import carla,numpy as np
 from PIL import Image
 from shapely.geometry import MultiPoint,Point,box
 from shapely.ops import unary_union
 from stop257_common_reference_pipeline_capture_v1 import PipelineCapture
 from stop257_native_place_sight_v1 import PlaceSight
 from stop257_reference_markings_geometry_v2 import spawn as spawn_zebra,observe as observe_markings
 from stop257_reference_markings_geometry_v1 import spawn as spawn_lines
 from stop257_fallback_geometry_observations_v1 import capture as capture_fallback_geometry
 from stop257_reference_geometry_observations_v1 import capture as capture_crosswalk_geometry
 from stop257_line_geometry_observations_v1 import capture as capture_line_geometry
 from stop257_stop_action_controller_v1 import Stop257Controller
 from cleanup import restore
 from delivery_values import values as channel_values,finish as finish_delivery
 from stop257_reference_native_inventory_v1 import NativeInventory
 cfg=json.loads((ROOT/'config.json').read_text());out=Path(args.output);out.mkdir(parents=True,exist_ok=True);assert (out/'runner.py').read_bytes()==Path(__file__).read_bytes();assert json.loads((out/'config.json').read_text())==cfg;assert {'kin.speed','rel.visible','st.sight_distance'}<=set(cfg['required_atoms']), 'Mandatory original capture primitives omitted';client=carla.Client('127.0.0.1',22100);client.set_timeout(180);owned=[];actors={};encoders={};logs={};cameras={};queues={};capture=None;inventory=None;contacts=[];error=None;changed=False;restoration=None;count=0;reference=None;last=None;first_inside=None;selected_frames=cfg["duration_s"]*20;cleared={};final_samples=[];duration_assessments=[];rows=[];channels={};reader=None;complete=False
 try:
  world=client.get_world();previous=world.get_settings();weather=world.get_weather();prior_xml=world.get_map().to_opendrive();prior_name=world.get_map().name
  if previous.synchronous_mode:raise ValueError('Endpoint not idle asynchronous')
  if any(a.type_id.startswith(('vehicle.','walker.','sensor.','controller.')) for a in world.get_actors()):raise ValueError('Dynamic actors remain before setup')
  prior_path=next(p for p in client.get_available_maps() if p.rsplit('/',1)[-1]==prior_name.rsplit('/',1)[-1]);(out/'previous-world.xodr').write_text(prior_xml);write(out/'previous-state.json',{'map':prior_name,'settings':str(previous),'weather':str(weather)});changed=True
  world=client.generate_opendrive_world((ROOT/'scene-stop257-v1.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False));settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10;world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon);mapping=world.get_map()
  branch=cfg['reference_branch'];allowed=['stop_sign_marked_line','no_line_marked_near_side_crosswalk','no_line_unmarked_sidewalk_connection_crosswalk','neither_line_nor_crosswalk_nearest_viewpoint_candidate']
  if branch not in allowed or cfg['observation_branch']['kind']!=branch:raise ValueError('Explicit actual reference branch required')
  markings=spawn_zebra(carla,world,False) if branch=='no_line_marked_near_side_crosswalk' else spawn_lines(carla,world,branch=='stop_sign_marked_line');owned.extend(markings)
  for _ in range(3):world.tick()
  write(out/'native-physical-road-markings.json',{'tiles':observe_markings(markings),'collisions_enabled':False,'method':'Actual physical line/crosswalk tiles for explicit selected branch. Separate East stop line retained. Query Native full vertices after ticks; no debug drawing.'})
  (out/'road.xodr').write_text(mapping.to_opendrive())
  if branch=='stop_sign_marked_line':reference_geometry=capture_line_geometry(carla,world,mapping,out,observe_markings(markings));geometry_name='native-line-geometry-before-motion.json'
  elif branch=='neither_line_nor_crosswalk_nearest_viewpoint_candidate':reference_geometry=capture_fallback_geometry(carla,world,mapping,out,observe_markings(markings));geometry_name='native-fallback-geometry-before-motion.json'
  else:reference_geometry=capture_crosswalk_geometry(carla,world,mapping,out,branch,observe_markings(markings));geometry_name='native-reference-geometry-before-motion.json'
  setup=[]
  surface=[]
  for x,y in [(-35,1.75),(-11.175,1.75),(0,1.75),(24,1.75),(1.75,94),(1.75,70),(1.75,40),(1.75,0),(1.75,-24)]:
   hits=world.cast_ray(carla.Location(x=x,y=y,z=5),carla.Location(x=x,y=y,z=-5));values=[{'label':str(h.label),'position_m':[h.location.x,h.location.y,h.location.z]} for h in hits];surface.append({'xy_m':[x,y],'hits':values})
   with (out/'native-surface-progress.jsonl').open('a') as raw:raw.write(json.dumps(surface[-1])+'\n')
   if not values or max(v['position_m'][2] for v in values)>.01:raise ValueError('Missing or obstructed native topmost operating surface before vehicle spawn')
  write(out/'native-surface-survey.json',{'rays':surface,'physical_intersection_edges_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'region_derivation':'Prolongation of Native surveyed roadway edges of two14m-wide orthogonal two-way roadways; never junction bbox alone.'})
  for role,x,y,yaw in [('ego',-35,1.75,0),('initial_crossing',1.75,cfg['initial_target_y_m']+24,-90),('further_crossing',1.75,94,-90)]:
   bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','stop257_'+role)
   if bp.has_attribute('color'):bp.set_attribute('color','30,220,50' if role=='ego' else '220,50,40' if role=='initial_crossing' else '50,70,220')
   actor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=.5),carla.Rotation(yaw=yaw)));owned.append(actor);actors[role]=actor;actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
  for i in range(40):
   frame=world.tick();setup.append({'frame':frame,'states':{r:state(a) for r,a in actors.items()}})
  write(out/'setup-settling.json',setup);initial={r:state(a) for r,a in actors.items()};pavement=unary_union([box(-160,-7,160,7),box(-7,-160,7,160)]);region=box(-7,-7,7,7)
  def body(s):return MultiPoint([(p[0],p[1]) for p in s['body_vertices_m']]).convex_hull
  for role,s in initial.items():
   if s['speed_mps']>.05 or not pavement.covers(body(s)):raise ValueError('Unsettled or unsupported full-body spawn '+role)
  ego=actors['ego'];front=ego.bounding_box.location.x+ego.bounding_box.extent.x
  observed_markings=observe_markings(markings)
  if branch=='stop_sign_marked_line':line_upstream=reference_geometry['applicable_upstream_x_m'];reference_kind='marked_stop_line'
  elif branch=='neither_line_nor_crosswalk_nearest_viewpoint_candidate':line_upstream=reference_geometry['nearest_candidate_native_x_m'];reference_kind='nearest_viewpoint_boundary_candidate'
  else:line_upstream=min(v[0] for v in reference_geometry['crosswalk_band_native_xy_m']);reference_kind='marked_near_side_crosswalk' if branch=='no_line_marked_near_side_crosswalk' else 'unmarked_sidewalk_connection_crosswalk'
  stop_center=line_upstream-front-cfg['reference_front_margin_request_m']
  write(out/'native-reference-context.json',{'branch':branch,'reference_kind':reference_kind,'applicable_west_stopline_present':branch=='stop_sign_marked_line','crosswalk_lateral_footways_present':branch!='neither_line_nor_crosswalk_nearest_viewpoint_candidate','reference_upstream_x_m':line_upstream,'source_geometry_receipts':cfg['reference_geometry_receipts'],'actual_before_motion_geometry':reference_geometry,'original_geometry_file':geometry_name,'modeled_driver_reference_local_m':[0,0,1.5],'reference_front_margin_request_m':cfg['reference_front_margin_request_m'],'anatomical_driver_eye_observed':False,'human_perception_observed':False,'nearest_relevant_legal_viewpoint_established':False,'required_saved_assessment':'Raw stopping error/displacement, entry/reference/clearance brackets, actual reference body/device pixels, separate Native potential-vehicle place queries and actual-user rays, every participant complete history. No legal epsilon, hazard, compliance or anatomical-perception finding.'})
  controller=Stop257Controller(cfg['initial_target_y_m'],stop_center,cfg['stop_mode'],cfg['rolling_speed_request_mps'],cfg['post_stop_speed_request_mps'])
  write(out/'native-vehicle-metadata.json',{r:{'state':s,'physics':str(actors[r].get_physics_control()),'driver_scope':'Explicit ordinary motor vehicle driver in actual physical control via native VehicleControl; synthetic person classification, no intent/perception finding'} for r,s in initial.items()});write(out/'engineering-controller-context.json',{'stop_center_x_m':stop_center,'actual_reference_branch':branch,'actual_reference_kind':reference_kind,'observed_upstream_reference_x_m':line_upstream,'requested_front_margin_m':cfg['reference_front_margin_request_m'],'engineering_stationary_detector':'Both crossing vehicles speed<.03m/s and target position within.2m for4samples schedules interaction in BOTH modes, independent of ego; not a legal cessation epsilon or span. Full ego velocity/displacement and controls retained.','reference_event':'First engineering crossing-vehicles-at-target stationary scheduling event, independent of ego behavior in both modes; counterpart occupancy and actual cessation/rolling measured independently.','further_controller':'Fixed further start94m/target70m; release at reference; brake while subject progresses, resume only after full subject body x>8m; physical choreography, no legal hazard/yield inference.','initial_controller':'Start target+24m, brake at target; release by common traffic-only observed reference. Subject full progression begins after initial full body y<-8m. Stop mode requests halt before actual selected reference; raw stop error and actual model-reference view are audited separately, without a legal epsilon or compliance finding. Actual body/velocity/displacement must confirm intended action and no premature intersection occupancy. Initial terminal-40/further-24m.','coordinate_contract':'Native CARLA XY; authored OpenDRIVE Y is negated.','duration_s':cfg['duration_s'],'frame_rate_hz':20})
  # Complete entrance/control inventory at setup; actor inventory retained every frame.
  devices=[]
  for a in world.get_actors():
   if a.type_id.startswith('traffic.'):
    t=a.get_transform();d={'actor_id':a.id,'type_id':a.type_id,'transform':str(t),'body_vertices_m':[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(t)]}
    if hasattr(a,'trigger_volume'):
     b=a.trigger_volume;d['trigger_volume']={'location':str(b.location),'extent':str(b.extent),'rotation':str(b.rotation),'native_vertices_m':[[v.x,v.y,v.z] for v in b.get_world_vertices(t)]}
     d['independent_approach_center_checks']=[]
     if a.type_id=='traffic.stop':
      for lane in [-1,-2] if t.location.x<0 else [1,2]:
       wp=mapping.get_waypoint_xodr(1 if t.location.x<0 else 2,lane,145 if t.location.x<0 else 8)
       d['independent_approach_center_checks'].append({'road':wp.road_id,'lane':wp.lane_id,'position_m':[wp.transform.location.x,wp.transform.location.y,wp.transform.location.z],'in_trigger_api':b.contains(wp.transform.location,t)})
    devices.append(d)
  write(out/'native-device-inventory.json',{'devices':devices,'actual_controlling_officer':'No human-direction actor/controller spawned; complete world inventory retained','traffic_signals':[d for d in devices if d['type_id'].startswith('traffic.traffic_light')],'native_map_connections':[[[a.road_id,a.lane_id,a.s],[b.road_id,b.lane_id,b.s]] for a,b in mapping.get_topology()],'administrative_status':'External synthetic non-through-highway/public-way/sign-authorization assumptions separately frozen; geometry/appearance does not establish them.'})
  for role,a in actors.items():
   sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=a);owned.append(sensor);sensor.listen(lambda e,r=role:contacts.append({'role':r,'frame':e.frame,'other_actor_id':e.other_actor.id,'normal_impulse':[e.normal_impulse.x,e.normal_impulse.y,e.normal_impulse.z]}))
  for name,w,h,fov,pose,attach in [('overview',3840,2160,90,carla.Transform(carla.Location(x=-5,y=35,z=145),carla.Rotation(pitch=-90)),None),('approach',1280,720,90,carla.Transform(carla.Location(x=-8,z=4),carla.Rotation(pitch=-15)),ego),('reference_corner',1280,720,90,carla.Transform(carla.Location(x=-19,y=0,z=10),carla.Rotation(pitch=-42)),None),('driver_reference',1280,720,cfg['driver_camera_FOV_deg'],carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation(yaw=45)),ego)]:
   bp=world.get_blueprint_library().find('sensor.camera.rgb')
   for k,v in [('image_size_x',str(w)),('image_size_y',str(h)),('fov',str(fov)),('sensor_tick','0')]:bp.set_attribute(k,v)
   camera=world.spawn_actor(bp,pose,attach_to=attach) if attach else world.spawn_actor(bp,pose);owned.append(camera);cameras[name]=camera;queues[name]=queue.Queue();camera.listen(queues[name].put);logs[name]=(out/(name+'.encoder.log')).open('x');encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',str(w)+'x'+str(h),'-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0','-level','1','-threads','2',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=logs[name])
  place_sampler=PlaceSight(carla,world,mapping,ego,maximum_m=cfg['place_sight_maximum_m'],step_m=cfg['place_sight_scan_step_m'],tolerance_m=cfg['place_sight_bracket_tolerance_m'])
  inventory=NativeInventory(world,mapping,out,Path(__file__),markings)
  write(out/'scenario_geometry.json',{'source':'Exact frozen stop257 OpenDRIVE roadway-edge construction and original Native full surface, topology and physical marking surveys','physical_verification':{'native_surface_survey':'native-surface-survey.json','native_markings':'native-physical-road-markings.json','actual_original_reference_geometry':geometry_name,'native_entrances':'native_incoming_lane_topology.json'},'intersection_polygon':[[-7,-7],[7,-7],[7,7],[-7,7]],'administrative_context':'Public-way status, sign authorization and through-highway designation are explicitly external synthetic assumptions, not inferred from geometry.'})
  capture=PipelineCapture(client,ego,out,cfg['case_id'],visibility=True,required_observations=cfg['required_atoms'])
  reader=(out/'capture/evidence.jsonl').open()
  (out/'channels').mkdir()
  channels={c['name']:(out/'channels'/(c['name']+'.jsonl')).open('x') for c in cfg['recording_description']['channels']}
  write(out/'context.json',cfg['recorded_context'])
  write(out/'authored_context_frozen.json',cfg['authored_test_context'])
  start=world.get_snapshot().timestamp.elapsed_seconds
  with (out/'native-motion.jsonl').open('x') as telemetry,(out/'video_frames.jsonl').open('x') as frames:
   for i in range(cfg['duration_s']*20):
    before={r:state(a) for r,a in actors.items()};requested=controller.step(i*.05,before)
    for role,command in requested.items():actors[role].apply_control(carla.VehicleControl(throttle=command['throttle'],brake=command['brake'],steer=command['steer'],hand_brake=command['hand_brake']))
    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start;states={r:state(a) for r,a in actors.items()};occupancy={r:{'center_inside':region.contains(Point(*s['position_m'][:2])),'body_overlap':region.intersects(body(s)),'full_body_inside':region.contains(body(s)),'native_body_boundary_distances_m':{'west':min(v[0] for v in s['body_vertices_m'])+7,'east':max(v[0] for v in s['body_vertices_m'])-7,'south':max(v[1] for v in s['body_vertices_m'])-7,'north':min(v[1] for v in s['body_vertices_m'])+7},'crossing_front_approach_distance_m':min(v[1] for v in s['body_vertices_m'])-7 if r!='ego' else None} for r,s in states.items()}
    row={'time_s':now,'frame':frame,'states':states,'occupancy':occupancy,'control_requests':requested,'engineering_phase':controller.phase,'body_inside_pavement':{r:pavement.covers(body(s)) for r,s in states.items()},'native_actor_inventory':[{'actor_id':a.id,'type_id':a.type_id} for a in world.get_actors()],'camera_metadata':{n:{'matrix':a.get_transform().get_matrix(),'inverse_matrix':a.get_transform().get_inverse_matrix(),'attributes':dict(a.attributes)} for n,a in cameras.items()},'contacts':list(contacts)}
    row['governing_native_inventory']=inventory.capture(frame,now)
    row['physical_road_marking_tiles']=observe_markings(markings);row['physical_stopline_tiles']=[t for t in row['physical_road_marking_tiles'] if 'physical_stopline_' in t['role']];row['physical_crosswalk_tiles']=[t for t in row['physical_road_marking_tiles'] if 'crosswalk_stripe_' in t['role']];row['subject_stopping_reference']={'kind':reference_kind,'upstream_x_m':line_upstream,'body_front_signed_distance_m':line_upstream-max(p[0] for p in states['ego']['body_vertices_m'])}
    row['camera_original_frames']={}
    for name,w,h in [('overview',3840,2160),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]:
     im=queues[name].get(timeout=30)
     while im.frame<frame:im=queues[name].get(timeout=30)
     if im.frame!=frame:raise ValueError('Original camera/frame mismatch')
     rgb=np.frombuffer(im.raw_data,dtype=np.uint8).reshape(h,w,4)[:,:,:3][:,:,::-1].copy();encoders[name].stdin.write(rgb.tobytes());row['camera_original_frames'][name]={'native_frame':im.frame,'sensor_timestamp':im.timestamp,'width':w,'height':h,'image_transform_matrix':im.transform.get_matrix(),'image_inverse_matrix':im.transform.get_inverse_matrix(),'source_rgb_sha256':hashlib.sha256(rgb.tobytes()).hexdigest()}
     if i%100==0 or i==cfg['duration_s']*20-1:Image.fromarray(rgb).save(out/(name+'-%04d.png'%i))
    row['driver_place_sight_distance']=place_sampler.capture(frame,now)
    capture.capture(frame,now,extra={'stop2572_native':row})
    event=json.loads(reader.readline());relations=event['original_observations']['relations'];assert len(relations)==2 and {r['b'] for r in relations}=={v['actor_id'] for k,v in row['states'].items() if k!='ego'} and all(r['a']==row['states']['ego']['actor_id'] and len(r['rays'])==9 for r in relations), 'Missing original actual-user body rays';observed=channel_values(row,event)
    for name,stream in channels.items():stream.write(json.dumps({'time_s':now,'value':observed[name]},allow_nan=False)+'\n');stream.flush()
    rows.append(row)
    telemetry.write(json.dumps(row,allow_nan=False)+'\n');telemetry.flush();frames.write(json.dumps({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':now})+'\n');frames.flush();count+=1;last=row
    if first_inside is None and occupancy['ego']['full_body_inside']:first_inside={'time_s':now,'frame':frame,'occupancy':occupancy}
    if controller.reference is not None and reference is None:reference=controller.reference;write(out/'measured-reference-event.json',reference)
    if i%100==0:print(json.dumps({'frame_index':i,'phase':controller.phase,'positions':{r:s['position_m'] for r,s in states.items()}}),flush=True)
    for role,s in states.items():
     fully_clear=min(v[0] for v in s['body_vertices_m'])>7 if role=='ego' else max(v[1] for v in s['body_vertices_m'])<-7
     if fully_clear and role not in cleared:cleared[role]=now
    final_samples.append({'time_s':now,'speeds':[s['speed_mps'] for s in states.values()]});final_samples=final_samples[-61:]
    if count in [v*20 for v in cfg.get('duration_candidates_s',[])]:
     adequate=len(cleared)==3 and now-max(cleared.values())>=3 and len(final_samples)>=60 and all(max(v['speeds'])<.03 for v in final_samples)
     assessment={'candidate_s':count/20,'observed_original_time_s':now,'all_full_body_clearance_s':dict(cleared),'final_observation_s':now-max(cleared.values()) if len(cleared)==3 else None,'engineering_final_response_complete':adequate,'legal_standard':False}
     duration_assessments.append(assessment)
     with (out/'duration-assessments.jsonl').open('a') as file:file.write(json.dumps(assessment)+'\n')
     if adequate:selected_frames=count;break
    if contacts or not all(row['body_inside_pavement'].values()):break
 except BaseException as e:error={'error':str(e),'traceback':traceback.format_exc()}
 finally:
  if inventory:inventory.close()
  if reader:reader.close()
  for stream in channels.values():stream.close()
  if capture:
   try:capture.close(confirmed=count==selected_frames and error is None)
   except BaseException as e:error=error or {'capture_close_error':str(e)}
  for name,encoder in encoders.items():
   try:encoder.stdin.close();code=encoder.wait(timeout=180);assert code==0
   except BaseException as e:error=error or {'encoder_error':str(e)}
   logs[name].close()
  if changed:
   try:restoration=restore(carla,client,world,owned,previous,weather,prior_path,prior_xml,'127.0.0.1',22100,out);write(out/'engine_scene_restored.json',restoration)
   except BaseException as e:error=error or {'restoration_error':str(e),'traceback':traceback.format_exc()}
  report={'kind':'stop2572_selected_Native_physical_report_not_pair_accepted','error':error,'frames':count,'expected_frames':selected_frames,'duration_assessments':duration_assessments,'actual_original_duration_s':None if last is None else last['time_s'],'full_recording':count==selected_frames,'contacts':contacts,'reference_event_observed':reference is not None,'first_subject_full_body_inside':first_inside,'final_engineering_phase':None if last is None else last['engineering_phase'],'restored':bool(restoration and restoration['restored']),'delivery_accepted':False,'requires_saved_audits':['All original temporal body/control histories','Actual stopping/displacement and measured reference brackets','Every counterpart full crossing/clearance and>=3s final observation','Full source videos/P6 actual body/sign/boundary and model-driver-view pixels, all original camera RGB hashes','Nearest candidate geometry plus actual driver-reference rays/pixels and stopping/entry/crossing brackets; no anatomical/perception or compliance inference','Actual Native place-sight source queries for potential crossing-road bodies and reciprocal eyes, bothdirections/allfourlanes, allframe source graph joins/censoring','Complete original Native/graph timestamp and identity joins']}
  write(out/'native-physical-report.json',report)
  complete=finish_delivery(out,cfg,rows,report,error)
 return 0 if complete else 2
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--output-dir',default=str(ROOT));parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=22100);args=parser.parse_args();cfg=json.loads((ROOT/'config.json').read_text())
 assert {'kin.speed','rel.visible','st.sight_distance'}<=set(cfg['required_atoms']);assert cfg['cell_id']=='C111325' and cfg['law']=='NRS-484B-257-2' and cfg['actor']=='motor_vehicle_driver';assert cfg['maximum_frames']==cfg['duration_s']*20;assert cfg['driver_camera_FOV_deg']==130 and cfg['native_construction_version']==2 and not cfg['duration_candidates_s'];assert args.host=='127.0.0.1' and args.port==22100
 if args.check:
  import carla,numpy,PIL,shapely.geometry
  from stop257_common_reference_pipeline_capture_v1 import PipelineCapture
  from stop257_native_place_sight_v1 import PlaceSight
  m=carla.Map('stop2572-offline',(ROOT/'scene-stop257-v1.xodr').read_text());landmarks=m.get_all_landmarks();assert len(landmarks)==1 and landmarks[0].road_id==1
  print(json.dumps({'passed':True,'law':'NRS-484B-257-2','cell':'C111325','actor':'motor_vehicle_driver','actual_reference_branch':cfg['reference_branch'],'West_STOP_only':True,'driver_FOV_deg':130,'live_connection_used':False,'per_original_physical_and_observation_checks_required':True}))
 else:args.output=args.output_dir;sys.exit(run(args))
