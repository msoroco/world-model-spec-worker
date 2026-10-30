"""One original causal following episode on the unchanged connected crest.
All measurements come from this episode; no driving replay or legal threshold.
"""
import argparse, hashlib, json, math, queue, signal, subprocess, sys, traceback
from pathlib import Path
from environment_capture import calibrate, surface_receipt, fields, write, sha, xyz, get_image
from following_controller import FollowingController, along_route_body_gap, route_distance, elevation
from entry_controller import EntryCarController,geometry as entry_geometry
ROOT=Path(__file__).resolve().parent
INTERRUPTED=[]

def line(f,v):
 f.write(json.dumps(v,allow_nan=False)+'\n');f.flush()
def clamp(x,a,b):return max(a,min(b,x))
def static(cfg):
 import importlib
 for module in ('native_following_capture','footprint_gap','environment_capture','following_controller','entry_controller','cleanup','pipeline_capture'):
  importlib.import_module(module)
 assert cfg['cell_id']=='C102372' and cfg['maximum_frames']==900 and cfg['fixed_delta_seconds']==.05
 assert cfg['additional_vehicle_count'] in (0,1)
 assert cfg['entry_controller_config']['cruise_reference_mps']==18. and cfg['entry_controller_config']['entry_offset_reference_m']==30.
 assert cfg['entry_controller_config']['lane_change_seconds']==4.
 assert cfg['width_role'] in ('subject','lead') and cfg['target_width_inch'] in (79,80,81)
 assert cfg['native_vehicle_blueprints'][cfg['width_role']]=='vehicle.carlamotors.european_hgv'
 assert cfg['native_vehicle_blueprints']['lead' if cfg['width_role']=='subject' else 'subject']=='vehicle.carlamotors.carlacola'
 asset=cfg['native_asset_configuration']
 for name,expected in asset['candidate_file_hashes'].items():assert sha(Path(asset['candidate_source_directory'])/name)==expected
 assert sha(ROOT/'scene.xodr')==cfg['map_sha256']
 assert 120 <= cfg['target_gap_m'] <= 180 and cfg['lead_cruise_mps'] in (5,7,9,11,13)
 assert all(0<=x<=100 for x in (cfg['weather']['precipitation'],cfg['weather']['fog_density']))
 assert 250<cfg['lead_start_station_m']<1000
 return {'passed':True,'map':'Unchanged1500m24m two-way physical crest, s750 maximum; complete connected approaches','worker_helpers_imported':True,'native_following_and_measurements':'must be verified in original episode','no_legal_standard':True}

def run(cfg,args):
 import carla,numpy as np
 from PIL import Image,ImageDraw
 from shapely.geometry import MultiPoint,box
 from pipeline_capture import PipelineCapture
 from native_following_capture import snapshot
 from cleanup import restore
 out=Path(args.output_dir);owned=[];streams={};cameras={};encoders={};history=[];contacts=[];capture=None
 previous=prior_xml=prior_path=prior_weather=world=None;changed=False;framefile=syncfile=reader=None;error=None;complete=False;setup=False;reason='initialization'
 client=carla.Client(args.host,args.port,2);client.set_timeout(180)
 try:
  world=client.get_world();previous=world.get_settings();assert not previous.synchronous_mode
  assert not [a for a in world.get_actors() if a.type_id.startswith(('vehicle.','walker.','sensor.','controller.'))]
  prior_xml=world.get_map().to_opendrive();prior_name=world.get_map().name;prior_weather=world.get_weather()
  prior_path=next(x for x in client.get_available_maps() if x.rsplit('/',1)[-1]==prior_name.rsplit('/',1)[-1])
  write(out/'previous-scene-state.json',{'map':prior_name,'settings':fields(previous),'weather':fields(prior_weather)});(out/'previous-world.xodr').write_text(prior_xml)
  changed=True;world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
  settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10;world.apply_settings(settings)
  ws=carla.WeatherParameters()
  for k,v in cfg['weather'].items():setattr(ws,k,v)
  world.set_weather(ws);mapping=world.get_map();(out/'road.xodr').write_text(mapping.to_opendrive())
  def spawn(bpname,s,lane,role):
   bp=world.get_blueprint_library().find(bpname);bp.set_attribute('role_name',role)
   if bp.has_attribute('color'):bp.set_attribute('color','0,255,0' if 'overtaking_entering' in role else '17,37,103')
   tr=mapping.get_waypoint_xodr(1,lane,s).transform;tr.location.z+=.5
   a=world.spawn_actor(bp,tr);owned.append(a);a.apply_control(carla.VehicleControl(brake=1,hand_brake=True));return a
  survey=[]
  for s in range(25,1476,25):
   for lane in (-1,1):
    wp=mapping.get_waypoint_xodr(1,lane,s);assert wp;loc=wp.transform.location
    hits=world.cast_ray(carla.Location(x=loc.x,y=loc.y,z=loc.z+10),carla.Location(x=loc.x,y=loc.y,z=loc.z-10));assert hits
    assert abs(max(h.location.z for h in hits)-loc.z)<.1,'Top native surface differs from authored route'
    survey.append({'s_m':s,'lane_id':lane,'position_m':xyz(loc),'width_m':wp.lane_width,'hits':[{'label':str(h.label),'position_m':xyz(h.location)} for h in hits]})
  write(out/'native_surface_survey.json',survey)
  mapsha=sha(out/'road.xodr');profile_survey=[]
  for station in range(450,1051,10):
   for lane in (-1,1):
    wp=mapping.get_waypoint_xodr(1,lane,station);loc=wp.transform.location;hits=world.cast_ray(carla.Location(x=loc.x,y=loc.y,z=loc.z+10),carla.Location(x=loc.x,y=loc.y,z=loc.z-10));assert hits and abs(max(h.location.z for h in hits)-loc.z)<.05
    profile_survey.append({'s_m':station,'lane_id':lane,'native_waypoint_m':xyz(loc),'native_rotation_deg':fields(wp.transform.rotation),'all_surface_hits':[{'label':str(h.label),'position_m':xyz(h.location)} for h in hits]})
  write(out/'native_hill_surface_survey.json',{'native_map_sha256':mapsha,'surface_samples':profile_survey})
  write(out/'native_road_profile.json',{'schema':'native-straight-road-profile-v1','map_sha256':mapsha,'survey_sha256':sha(out/'native_hill_surface_survey.json'),'instrumentation_sha256':sha(ROOT/'runner.py'),'half_road_width_m':12,'grade_patch_length_m':2,'crest_ridge_mesh_width_m':.25})
  # Verify the actual private native package overlay before any subject spawn.
  overlay_path=Path(cfg['owned_runtime_root'])/'private-native-asset-overlay.json'
  overlay=json.loads(overlay_path.read_text())
  observed_hashes={Path(k).name:v['candidate_sha256'] for k,v in overlay['files'].items()}
  assert observed_hashes==cfg['native_asset_configuration']['candidate_file_hashes'],'Actual owned runtime does not contain frozen native geometry'
  for filename,expected in observed_hashes.items():
   actual=Path(cfg['owned_runtime_root'])/'runtime/CarlaUE4/Content/Carla/Blueprints/Vehicles/European_HGV'/filename
   assert sha(actual)==expected
  write(out/'verified_native_asset_configuration.json',{'frozen':cfg['native_asset_configuration'],'actual_owned_overlay':overlay,'native_factory_attribute_limitation':'European_HGV factory metadata still says6wheels/generation2; physicalderivedCarlaCola has4wheels andsourcegeometry. Preserve rawmetadata andactualnativephysics separately, do not infer bodyfromslotname.'})
  instrument=spawn('vehicle.lincoln.mkz_2020',1270,1,'separate_optical_setup_target')
  for _ in range(50):world.tick()
  calibration=calibrate(world,instrument,out,owned)
  # The original optical instrument is on one constant-grade approach. It is
  # neither a crest sight-distance test nor an extra recorded traffic actor.
  assert calibration['crest_transfer']['minimum_observer_station_m']>=850
  assert instrument.destroy();owned.remove(instrument)
  for _ in range(2):world.tick()
  assert not [a for a in world.get_actors() if a.type_id.startswith(('vehicle.','sensor.'))]
  apparatus=spawn(cfg['native_vehicle_blueprints']['lead'],cfg['lead_start_station_m'],-1,'moving_goods_truck_lead')
  ego_bp=world.get_blueprint_library().find(cfg['native_vehicle_blueprints']['subject'])
  # Evaluate the actual blueprint instance bounding box using a temporary spawn
  # only once; all body-reference adjustments happen before recorded movement.
  ego=spawn(cfg['native_vehicle_blueprints']['subject'],cfg['lead_start_station_m']-cfg['target_gap_m']-7,-1,'heavy_physical_control_goods_truck_subject')
  assert ego.type_id==cfg['native_vehicle_blueprints']['subject'] and apparatus.type_id==cfg['native_vehicle_blueprints']['lead']
  # Native spawn transform is available only after a simulator tick. Both actors remain handbraked; no driving episode has begun.
  for _ in range(50):world.tick()
  lo=cfg['lead_start_station_m']-cfg['target_gap_m']-15;hi=cfg['lead_start_station_m']-cfg['target_gap_m']
  for _ in range(50):
   s=(lo+hi)/2;tr=mapping.get_waypoint_xodr(1,-1,s).transform;tr.location.z+=.5
   g=along_route_body_gap([xyz(p) for p in ego.bounding_box.get_world_vertices(tr)],[xyz(p) for p in apparatus.bounding_box.get_world_vertices(apparatus.get_transform())])
   if g>cfg['target_gap_m']:lo=s
   else:hi=s
  # Direct native spawn preserves prospective root mesh scale; set_transform applies a unit actor scale.
  # Destroy the initial stationary sizing probe and spawn a new real truck at the computed station.
  assert ego.destroy();owned.remove(ego)
  ego=spawn(cfg['native_vehicle_blueprints']['subject'],s,-1,'heavy_physical_control_goods_truck_subject')
  extra=[]
  if cfg['additional_vehicle_count']:extra.append(spawn('vehicle.lincoln.mkz_2020',s-28.,-1,'ordinary_overtaking_entering_car'))
  for a in (ego,apparatus,*extra):
   if cfg.get('tire_friction') is not None:
    physics=a.get_physics_control()
    for wheel in physics.wheels:wheel.tire_friction=cfg['tire_friction']
    a.apply_physics_control(physics)
  for _ in range(50):world.tick()
  surface_receipt(world,mapping,out,ROOT/'scene.xodr',[Path(p) for p in cfg['surface_asset_paths']])
  calhash=sha(out/'environment_calibration.json');surfhash=sha(out/'surface_provenance.json')
  initial={str(a.id):{'id':a.id,'role':'ego' if a==ego else 'apparatus' if a==apparatus else 'surrounding','initial_state':snapshot(a),'physics':fields(a.get_physics_control()),'wheels':[fields(w) for w in a.get_physics_control().wheels]} for a in (ego,apparatus,*extra)}
  
  for a in (ego,apparatus,*extra):
   ph=a.get_physics_control();initial[str(a.id)]['native_transmission']={'forward_gears':[{'ratio':g.ratio,'down_ratio':g.down_ratio,'up_ratio':g.up_ratio} for g in ph.forward_gears],'torque_curve':[[v.x,v.y] for v in ph.torque_curve],'native_automatic_transmission':'Native automatic gears; mass,torque curves and ratios unchanged; actual gear/control history retained'}
  write(out/'vehicle_metadata.json',initial);write(out/'actual_scene_identity.json',{'map_name':mapping.name,'map_sha256':sha(out/'road.xodr'),'subject_actor_id':ego.id,'lead_actor_id':apparatus.id,'synthetic_context':cfg['authored_test_context'],'optical_setup_removed_before_recording':True})
  def mesh_bounds():
   # Native get_level_bbs dispatches to full LOD0 mesh-vertex bounds, separate
   # from Actor.bounding_box/VehicleBounds metadata. No authored extent override.
   boxes=world.get_level_bbs(carla.CityObjectLabel.Truck)
   assert len(boxes)==2,('Native truck geometry inventory incomplete',len(boxes))
   result=[]
   for actor in (ego,apparatus):
    pose=actor.get_transform();body=[xyz(v) for v in actor.bounding_box.get_world_vertices(pose)];centre=[sum(v[k] for v in body)/8 for k in range(3)]
    b=min(boxes,key=lambda b:sum((xyz(b.location)[k]-centre[k])**2 for k in range(3)))
    assert math.dist(xyz(b.location),centre)<1.,'Native mesh/actor body association ambiguous'
    vertices=[xyz(v) for v in b.get_world_vertices(carla.Transform())]
    local=[];inverse=pose.get_inverse_matrix()
    for vertex in vertices:local.append([sum(inverse[k][j]*[*vertex,1][j] for j in range(4)) for k in range(3)])
    width=max(v[1] for v in local)-min(v[1] for v in local)
    role='subject' if actor.id==ego.id else 'lead'
    assert abs(width-2*actor.bounding_box.extent.y)<.002,('Native mesh/metadata width mismatch',width,2*actor.bounding_box.extent.y)
    if role==cfg['width_role']:assert abs(width-cfg['target_width_inch']*.0254)<=.002,('Actual native width target unconfirmed',role,width)
    else:assert width>=2.032,('Held counterpart must be genuinely qualifying',role,width)

    result.append({'actor_id':actor.id,'semantic_label':'Truck','native_mesh_box_centre_m':xyz(b.location),'native_mesh_box_rotation_deg':fields(b.rotation),'native_mesh_box_extent_m':xyz(b.extent),'native_mesh_box_world_vertices_m':vertices,'mesh_bound_width_in_actor_frame_m':width,'box_metadata_width_m':2*actor.bounding_box.extent.y,'method':'world.get_level_bbs(Truck); native full LOD0 vertex bounds and component transforms; project all8 native meshbound vertices to actual actor local lateral axis; finite native float envelope, not statutory measurement convention'})
   assert len({v['actor_id'] for v in result})==2
   return result
  write(out/'native_mesh_width_setup.json',mesh_bounds())
  initial_gap=along_route_body_gap(snapshot(ego)['body_vertices_native_m'],snapshot(apparatus)['body_vertices_native_m']);assert abs(initial_gap-cfg['target_gap_m'])<.3,('Initial native gap',initial_gap)
  camdefs=[('driver',ego,carla.Transform(carla.Location(x=-7,z=4.5),carla.Rotation(pitch=-15))),('lead',apparatus,carla.Transform(carla.Location(x=-11,z=6),carla.Rotation(pitch=-15))),('overview',ego,carla.Transform(carla.Location(x=(cfg['target_gap_m']+2*ego.bounding_box.extent.x)/2,z=(35 if cfg['additional_vehicle_count'] else 28)),carla.Rotation(pitch=-90)))]
  camdefs.extend([('width_subject',ego,carla.Transform(carla.Location(x=-7,z=2.8),carla.Rotation(pitch=-6))),('width_lead',apparatus,carla.Transform(carla.Location(x=-7,z=2.8),carla.Rotation(pitch=-6)))])
  if extra:camdefs.append(('traffic',extra[0],carla.Transform(carla.Location(x=-7,z=4),carla.Rotation(pitch=-15))))
  for name,parent,tr in camdefs:
   bp=world.get_blueprint_library().find('sensor.camera.rgb')
   for k,v in [('image_size_x','3840' if name=='overview' else '1920' if name.startswith('width_') else '960'),('image_size_y','2160' if name=='overview' else '1080' if name.startswith('width_') else '540'),('fov','165' if name=='overview' else '60' if name.startswith('width_') else '90'),('sensor_tick','0')]:bp.set_attribute(k,v)
   camera=world.spawn_actor(bp,tr,attach_to=parent);owned.append(camera);q=queue.Queue();camera.listen(q.put);cameras[name]=(camera,q)
  for a in (ego,apparatus,*extra):
   sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=a);owned.append(sensor);sensor.listen(lambda e,who=a.id:contacts.append({'actor_id':who,'frame':e.frame,'other_actor_id':e.other_actor.id,'impulse':xyz(e.normal_impulse)}))
  for _ in range(3):world.tick()
  for camera,q in cameras.values():
   while not q.empty():q.get_nowait()
  desc=cfg['recording_description'];(out/'channels').mkdir();(out/'rgb').mkdir()
  for c in desc['channels']:streams[c['name']]=(out/'channels'/(c['name']+'.jsonl')).open('x')
  framefile=(out/'video_frames.jsonl').open('x');syncfile=(out/'synchronized_motion_records.jsonl').open('x')
  context={x['name']:{'declared_unit':x['unit'],'value':{'source':'Exact native scene, original metadata and authored configuration','native_scene':'actual_scene_identity.json','surface':'surface_provenance.json','environment':'environment_calibration.json','vehicle_physics':'vehicle_metadata.json','road_geometry':'road.xodr','survey':'native_surface_survey.json','synthetic_context':cfg['authored_test_context'],'measurement_reference':{'dt_s':.05,'Core_t':'round(original_time_s*1000)','world_axes':'Native CARLA XYZ; Core reflects y','gap':'Extrema of all8 actual body vertices projected to unchanged straight3D centreline; polygon gap is separate'}}} for x in desc['context_inputs']};write(out/'context.json',context)
  for name,size in [(name,'3840x2160' if name=='overview' else '1920x1080' if name.startswith('width_') else '960x540') for name in cameras]+[('review','1920x1680')]:
   log=(out/(name+'.encoder.log')).open('x');proc=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',size,'-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1','-coder','0','-context','0','-threads','2',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=log);encoders[name]=(proc,log)
  capture=PipelineCapture(client,ego,out,cfg['case_id'],visibility=True,required_observations=cfg['required_atoms']);reader=(out/'capture/evidence.jsonl').open();start=world.get_snapshot().timestamp.elapsed_seconds;states={a.id:0. for a in (apparatus,*extra)};follower=FollowingController(float(cfg['target_gap_m']));overtaker=EntryCarController(**cfg['entry_controller_config']);setup=True
  def steering(a,lane):
   wp=mapping.get_waypoint_xodr(1,lane,clamp(a.get_location().x,1,1499));desired=math.radians(wp.transform.rotation.yaw);yaw=math.radians(a.get_transform().rotation.yaw);he=(desired-yaw+math.pi)%(2*math.pi)-math.pi;cross=math.cos(desired)*(a.get_location().y-wp.transform.location.y);return clamp(-.35*cross+1.2*he,-.5,.5)
  def speed_control(a,target,lane):
   speed=a.get_velocity().length();err=target-speed;trial=clamp(states[a.id]+err*.05,-5,5);feedforward=.35 if a.id==apparatus.id and target>0 else 0.;limit=1.;output=feedforward+.6*err+.15*trial
   if not ((output>limit and err>0) or (output<-1 and err<0)):states[a.id]=trial
   output=feedforward+.6*err+.15*states[a.id]
   if target==0:return carla.VehicleControl(brake=.7,hand_brake=speed<.05,steer=steering(a,lane))
   return carla.VehicleControl(throttle=clamp(output,0,1.),brake=clamp(-output,0,1),steer=steering(a,lane))
  for i in range(900):
   elapsed=i*.05;target=0. if elapsed<2 or elapsed>=34 else max(0.,cfg['lead_cruise_mps']-cfg['lead_speed_drop_mps']) if 22<=elapsed<28 else min(cfg['lead_cruise_mps'],max(0.,elapsed-2.)*cfg['lead_acceleration_request_mps2']) if elapsed<22 else cfg['lead_cruise_mps']
   before={'frame':world.get_snapshot().frame,'time_s':elapsed,'ego':snapshot(ego),'apparatus':snapshot(apparatus),'extra_traffic':[snapshot(v) for v in extra]}
   def state(v):return {'actor_id':v['actor_id'],'position_m':v['position_m'],'velocity_mps':v['velocity_mps'],'body_vertices_m':v['body_vertices_native_m'],'applied_control':v['applied_control']}
   fb=follower.step(before['frame'],elapsed,state(before['ego']),state(before['apparatus']))
   ec=carla.VehicleControl(throttle=fb['throttle'],brake=fb['brake'],hand_brake=fb['hand_brake'],steer=steering(ego,-1))
   car_request=None;override={'active':False,'engineering_minimum_front_gap_m':8.,'scope':'Actualnearest-fronttrafficfeedback, notlegalfollowing/dangerstandard'}
   if extra:
    car_request=overtaker.step(before['frame'],elapsed,before['extra_traffic'][0],before['ego'],before['apparatus']);g=car_request['geometry']
    override.update(actual_car_state=before['extra_traffic'][0],actual_geometry=g)
    if g['car_any_body_overlaps_lane_minus1'] and 0<g['car_rear_after_ego_front_m']<8:ec.throttle=0.;ec.brake=1.;override['active']=True
   controls=[carla.command.ApplyVehicleControl(ego.id,ec),carla.command.ApplyVehicleControl(apparatus.id,speed_control(apparatus,target,-1))]
   if extra:
    cr=car_request;controls.append(carla.command.ApplyVehicleControl(extra[0].id,carla.VehicleControl(throttle=cr['throttle'],brake=cr['brake'],steer=cr['steer'],hand_brake=cr['hand_brake'])))
    lights=carla.VehicleLightState.LeftBlinker if cr['phase']=='left_pass' else carla.VehicleLightState.RightBlinker if cr['phase']=='merge' else carla.VehicleLightState.NONE
    extra[0].set_light_state(lights)

   assert not any(r.has_error() for r in client.apply_batch_sync(controls,False));frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
   observed_weather=fields(world.get_weather());assert observed_weather==calibration['weather']
   env={'frame':frame,'time_s':now,'weather':observed_weather,'visibility_m':calibration['visibility_m'],'ice_or_snow':False,'calibration_sha256':calhash,'surface_sha256':surfhash}
   a,b=snapshot(ego),snapshot(apparatus);others=[snapshot(v) for v in extra];poly=[MultiPoint([(p[0],p[1]) for p in v['body_vertices_native_m']]).convex_hull for v in (a,b,*others)]
   gap=along_route_body_gap(a['body_vertices_native_m'],b['body_vertices_native_m']);wheels=[w.tire_friction for w in ego.get_physics_control().wheels]
   scalars={'subject_overall_width':2*ego.bounding_box.extent.y,'lead_overall_width':2*apparatus.bounding_box.extent.y,'ego_speed':a['speed_mps'],'leader_speed':b['speed_mps'],'along_route_body_gap':gap,'euclidean_body_separation':poly[0].distance(poly[1]),'relative_speed':a['speed_mps']-b['speed_mps'],'surrounding_vehicle_count':len(others),'native_precipitation_strength':observed_weather['precipitation'],'native_fog_density':observed_weather['fog_density'],'observed_tire_friction':sum(wheels)/len(wheels)}
   # Complete native attachment inventory, independently of RGB sensor parents.
   inventory_actors=list(world.get_actors())
   hierarchy=[{'actor_id':v.id,'type_id':v.type_id,'parent_actor_id':v.parent.id if v.parent is not None else None} for v in inventory_actors]
   vehicles=[v for v in inventory_actors if v.type_id.startswith('vehicle.')]
   assert set(v.id for v in vehicles)=={v.id for v in (ego,apparatus,*extra)}
   configuration={'native_asset_configuration':cfg['native_asset_configuration'],'schema':'native-single-chassis-entry-configuration-v1','frame':frame,'time_s':now,'actor_hierarchy':hierarchy,'vehicles':[],'construction':'Two directlyspawned qualifiedsingle-chassis cargo trucks plus0/1actualsingle-chassispassengerovertaker; no trailer/constraint ortrafficmanager. CompleteNativeactorhierarchy/wheels/IDs retained, not a generaltrailer detector.'}
   for v in vehicles:
    assert v.parent is None and len(v.get_physics_control().wheels)==4
    assert v.type_id in set(cfg['native_vehicle_blueprints'].values())|{'vehicle.lincoln.mkz_2020'}
    configuration['vehicles'].append({'actor_id':v.id,'blueprint':v.type_id,'parent_actor_id':None,'wheel_count':len(v.get_physics_control().wheels),'configuration':'single_rigid_goods_truck' if v.id in (ego.id,apparatus.id) else 'single_rigid_passenger_overtaker','trailer_or_combination':False,'native_factory_wheel_count_metadata':v.attributes.get('number_of_wheels'),'observed_physics_wheel_count':len(v.get_physics_control().wheels),'provenance':'Trucks: verified actualCarlaColacargo body/frozencookedpackage andnativefourwheelphysics, rawderivedfactorysixwheelmetadata retained. Passenger: actualNativeLincoln asset/instancebody/attributes/4wheels/photographs; no goodsuseclaimed. ActualNativeID/parent/body andcompleteinventory everyframe; no name-onlyqualification.'})
   packet={'frame':frame,'time_s':now,'ego':a,'apparatus':b,'extra_traffic':others,'environment_measurements':env,'contacts':list(contacts),'pre_control_state':before,'follower_controller':fb,'commanded_leader_speed_mps':target,'target_gap_m':cfg['target_gap_m'],'along_route_body_gap_m':gap,'Euclidean_polygon_separation_m':poly[0].distance(poly[1]),'native_component_gap_m':None,'whole_body_inside_roadway':all(box(0,-12,1500,12).covers(p) for p in poly),'ego_and_lead_inside_same_direction_lane':all(box(0,0,1500,12).covers(p) for p in poly[:2]),'measured_scalars':scalars,'observed_ego_wheel_tire_friction':wheels,'native_actor_inventory':[{'id':v.id,'type':v.type_id} for v in inventory_actors],'native_vehicle_configuration':configuration,'native_mesh_bounds':mesh_bounds()}
   native_s=float(ego.get_location().x);za=mapping.get_waypoint_xodr(1,-1,native_s-.25).transform.location.z;zb=mapping.get_waypoint_xodr(1,-1,native_s+.25).transform.location.z
   native_profile={'frame':frame,'time_s':now,'map_sha256':mapsha,'s_m':native_s,'native_z_before_after_m':[za,zb]}
   packet.update(overtaker_controller_request=car_request,ego_additional_traffic_feedback=override,entry_geometry=entry_geometry(a,b,others[0]) if others else None,pre_control_states=before,ego_final_requested_control={'throttle':ec.throttle,'brake':ec.brake,'steer':ec.steer,'hand_brake':ec.hand_brake},pairwise_planar_body_separations_m=[{'actor_a':u['actor_id'],'actor_b':v['actor_id'],'gap_m':poly[ii].distance(poly[jj])} for ii,u in enumerate([a,b]+others) for jj,v in enumerate([a,b]+others) if ii<jj],native_component_pair_gaps=None)
   capture.capture(frame,now,extra={'following_native':packet,'environment_measurements':env,'scene_actor_inventory':packet['native_actor_inventory'],'native_road_profile':native_profile});event=json.loads(reader.readline());packet['geometric_sight_distance']=event['visibility'];packet['native_road_projection']=event['world']['road_projection'];history.append(packet);line(syncfile,{'time_s':now,'value':packet})
   lane_rows=[]
   for who,actor in [('subject',ego),('lead',apparatus)]+[('overtaker',v) for v in extra]:
    station=actor.get_location().x
    for lane_id in (-1,1):
     wp=mapping.get_waypoint_xodr(1,lane_id,station)
     lane_rows.append({'relative_to':who,'station_m':station,'road_id':wp.road_id,'lane_id':wp.lane_id,'lane_type':str(wp.lane_type),'width_m':wp.lane_width,'native_forward':xyz(wp.transform.get_forward_vector()),'markings':{'left':str(wp.left_lane_marking.type),'right':str(wp.right_lane_marking.type)},'available':True,'availability_provenance':'Authored no closure; native driving lane exists; complete actual traffic inventory retained','next_lane_connections':[{'road_id':x.road_id,'lane_id':x.lane_id} for x in wp.next(1.)]})
   motion_context={'participants':[a,b]+others,'actual_controls':[x['applied_control'] for x in [a,b]+others],'available_lanes':lane_rows,'space_route_interval_m':{'rear':route_distance(max(v[0] for v in a['body_vertices_native_m'])),'front':route_distance(min(v[0] for v in b['body_vertices_native_m']))},'entered_overtaking_vehicle_ids':[v['actor_id'] for v in others] if others and packet['entry_geometry']['car_full_body_occupies_space'] else [],'actual_overtaking_activity':{'Nativeparticipants':others,'controller_request':car_request,'observed_entry_geometry':packet['entry_geometry'],'actual_nearest_front_actor_id':packet['entry_geometry']['actual_nearest_front_actor_id'] if others else b['actor_id'],'designated_truck_reference_actor_id':b['actor_id']},'limitation':'Actualfinitebodyfootprint/motion, not conditionspermit/danger orlegalimmediacydefinition; full50mssourcesretained.'}
   for c in desc['channels']:
    name=c['name'];value=scalars[name] if name in scalars else fb['actual_controller_inputs'] if name=='following_controller_inputs' else env if name=='highway_condition_history' else packet['geometric_sight_distance'] if name in ('visibility_history','st.sight_distance') else packet
    if name=='lane_availability_history':value={'frame':frame,'lanes':lane_rows,'same_direction_available_lane_count':1,'direction_reference':'Actual native subject forward direction'}
    if name in ('entry_occupancy_geometry','overtaking_history'):value=motion_context
    if name=='participant_motion':value={'frame':frame,'ego':a,'apparatus':b,'extra_traffic':others}
    if name=='traffic_inventory':value={'frame':frame,'participants':[a,b]+others,'native_actor_inventory':packet['native_actor_inventory']}
    line(streams[name],{'time_s':now,'value':value})
   images={};camera_states={}
   for name,(camera,q) in cameras.items():
    im=get_image(q,frame);images[name]=Image.fromarray(np.frombuffer(im.raw_data,dtype=np.uint8).reshape(im.height,im.width,4)[:,:,:3][:,:,::-1]);camera_states[name]={'actor_id':camera.id,'pose_matrix':camera.get_transform().get_matrix(),'inverse_matrix':camera.get_transform().get_inverse_matrix(),'attributes':dict(camera.attributes)}
   line(framefile,{'video_frame':i,'carla_frame':frame,'time_s':now,'cameras':camera_states})
   canvas=Image.new('RGB',(1920,1680),'#151515')
   for name,position in [('driver',(0,60)),('lead',(960,60)),('overview',(0,600)),('traffic',(960,600)),('width_subject',(0,1140)),('width_lead',(960,1140))]:
    if name in images:canvas.paste(images[name].resize((960,540)),position)
   draw=ImageDraw.Draw(canvas)
   draw.text((980,740),'Actual model width subject %.6fm / lead %.6fm; native body frame'%(scalars['subject_overall_width'],scalars['lead_overall_width']),fill='white')
   draw.text((980,765),'Width %s reference %.1fin; full original width cameras retained'%(cfg['width_role'],cfg['target_width_inch']),fill='white')
   draw.text((12,8),cfg['case_id']+' | original t %.2fs | body gap %.2fm | ego %.2f / lead %.2fm/s'%(now,gap,a['speed_mps'],b['speed_mps']),fill='white');draw.text((12,28),'Native crest / two goods trucks / observed-state feedback | conditions permit and danger unresolved',fill='white')
   if 'traffic' not in images:
    draw.text((980,630),'Native ego chase / moving overhead / native lead-truck chase',fill='white');draw.text((980,655),'Requested body gap %.1fm; observed %.2fm'%(cfg['target_gap_m'],gap),fill='white');draw.text((980,680),'Original45s20Hz; all body/traffic/condition histories retained',fill='white')
   if i in (0,40,100,280,400,440,480,560,680,750,899):
    for name,im in images.items():im.save(out/'rgb'/('%s-%06d.png'%(name,i)))
   for name,im in dict(images,review=canvas).items():encoders[name][0].stdin.write(im.tobytes())
   if i%100==0:print(json.dumps({'frame_index':i,'time_s':now,'gap_m':gap,'ego_mps':a['speed_mps'],'leader_mps':b['speed_mps']}),flush=True)
   if contacts:reason='collision';break
   if not packet['whole_body_inside_roadway'] or not packet['ego_and_lead_inside_same_direction_lane']:reason='roadway_departure';break
   if any(abs(v.get_transform().rotation.roll)>30 for v in (ego,apparatus,*extra)):reason='loss_of_control';break
   if gap<=0:reason='lost_following_order';break
   if INTERRUPTED:reason='interrupted';break
  else:
   occupied=[h for h in history if h.get('entry_geometry') and h['entry_geometry']['car_full_body_occupies_space']]
   overtook=any(h.get('entry_geometry') and h['entry_geometry']['car_rear_after_ego_front_m']>0 and h['extra_traffic'][0]['position_m'][1]<0 for h in history)
   complete=ego.get_velocity().length()<.1 and apparatus.get_velocity().length()<.1 and all(v.get_velocity().length()<.1 for v in extra) and (not extra or (len(occupied)>=100 and overtook))
   reason='completed_actual_entry_occupancy_following_response_braking_episode' if complete else 'entry_or_stopping_outcome_incomplete'
  reader.close();reader=None;capture.close(confirmed=complete);capture=None
 except BaseException as exc:
  error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()};reason='construction_or_capture_failure'
 finally:
  if capture:
   try:capture.close(confirmed=False)
   except Exception:pass
  if reader:reader.close()
  for f in list(streams.values())+[framefile,syncfile]:
   if f:f.close()
  videos=[]
  for name,(proc,log) in encoders.items():
   try:proc.stdin.close();assert proc.wait(timeout=180)==0;videos.append(name+'.mkv')
   except BaseException as exc:
    if error is None:error={'type':'encoding_failure','message':str(exc)}
   log.close()
  if changed and prior_xml is not None:
   try:write(out/'engine_scene_restored.json',restore(carla,client,world,owned,previous,prior_weather,prior_path,prior_xml,args.host,args.port,out))
   except BaseException as exc:
    if error is None:error={'type':'restoration_failure','message':str(exc),'traceback':traceback.format_exc()}
  steady=[h for h in history if 14<=h['time_s']<=20];gap_match=len(steady)>=100 and all(abs(h['along_route_body_gap_m']-cfg['target_gap_m'])<=2 for h in steady)
  speed_match=len(steady)>=100 and all(abs(h['apparatus']['speed_mps']-cfg['lead_cruise_mps'])<=.6 and abs(h['ego']['speed_mps']-cfg['lead_cruise_mps'])<=.6 for h in steady)
  restored=(out/'engine_scene_restored.json').exists() and json.loads((out/'engine_scene_restored.json').read_text()).get('restored')
  checks=[{'target':'following_body_gap','requested':cfg['target_gap_m'],'measured':{'steady_min_m':min([h['along_route_body_gap_m'] for h in steady] or [0]),'steady_max_m':max([h['along_route_body_gap_m'] for h in steady] or [0]),'samples':len(steady)},'method':'Actual all8nativebodyvertex3Droute gap every sample14..20s','tolerance':{'gap_m':2.,'minimum_interval_s':5},'matched':bool(gap_match),'physical_cause_confirmed':setup,'cause_evidence':['synchronized_motion_records.jsonl']},
   {'target':'both_actual_cruise_speeds','requested':cfg['lead_cruise_mps'],'measured':{'lead_min_max_mps':[min([h['apparatus']['speed_mps'] for h in steady] or [0]),max([h['apparatus']['speed_mps'] for h in steady] or [0])],'ego_min_max_mps':[min([h['ego']['speed_mps'] for h in steady] or [0]),max([h['ego']['speed_mps'] for h in steady] or [0])]},'method':'Actual native velocity norms every sample14..20s','tolerance':.6,'matched':bool(speed_match),'physical_cause_confirmed':setup,'cause_evidence':['synchronized_motion_records.jsonl']},
   {'target':'full_original_episode','requested':900,'measured':len(history),'method':'Complete45s20Hz following,actualleaderchange,followerresponse,brakingandstoppedoutcome','tolerance':0,'matched':bool(complete and len(history)==900 and error is None and restored),'physical_cause_confirmed':setup,'cause_evidence':['video_frames.jsonl','synchronized_motion_records.jsonl']}]
  matched=all(c['matched'] for c in checks) and error is None
  width_values=[h['measured_scalars']['subject_overall_width' if cfg['width_role']=='subject' else 'lead_overall_width'] for h in history]
  checks.append({'target':'native_body_frame_width','requested':cfg['target_width_inch']*.0254,'measured':{'min_m':min(width_values or [0]),'max_m':max(width_values or [0]),'samples':len(width_values)},'method':'Actual native actor width verified against independent full LOD0 mesh bounds every originalframe; body-frame model envelope, not Core projected extent or inventedstatutoryconvention','tolerance':.002,'matched':len(width_values)==900 and all(abs(v-cfg['target_width_inch']*.0254)<=.002 for v in width_values),'physical_cause_confirmed':bool(history),'cause_evidence':['synchronized_motion_records.jsonl','verified_native_asset_configuration.json','native_mesh_width_setup.json']})
  occupancy=[h for h in history if h.get('entry_geometry') and h['entry_geometry']['car_full_body_occupies_space']];overtook=any(h.get('entry_geometry') and h['entry_geometry']['car_rear_after_ego_front_m']>0 and h['extra_traffic'][0]['position_m'][1]<0 for h in history)
  checks.append({'target':'actual_overtaking_entry_and_occupancy','requested':cfg['additional_vehicle_count'],'measured':{'overtook_subject_in_left_lane':overtook,'whole_car_occupancy_frames':len(occupancy),'first_last_occupied_original_s':[occupancy[0]['time_s'],occupancy[-1]['time_s']] if occupancy else None},'method':'Actualall8Nativecar/truckbodyvertices andrealmotion; no command-as-observation or dangerverdict','tolerance':{'minimum_occupied_frames':100,'sample_s':.05},'matched':not cfg['additional_vehicle_count'] or (overtook and len(occupancy)>=100),'physical_cause_confirmed':bool(history),'cause_evidence':['synchronized_motion_records.jsonl','channels/entry_occupancy_geometry.jsonl','channels/overtaking_history.jsonl']})
  result={'primary_video_reference':'review.mkv','status':'draft','cell_id':'C102372','actor':'heavy_vehicle_driver','case_id':cfg['case_id'],'input_revision':cfg['input_revision'],'setup_confirmed':setup,'behavior_attempted':any(h['ego']['speed_mps']>.01 for h in history),'maneuver_completed':complete,'termination_reason':reason,'physical_failure_flags':{'collision':bool(contacts),'roadway_departure':reason=='roadway_departure','loss_of_control':reason=='loss_of_control','lost_following_order':reason=='lost_following_order'},'target_checks':checks,'measurement_limits':{'width':'Native body bounding-box envelope; visible protrusions/mesh uncertainty not fully bounded.','gap':'All8boxvertex projection; engineering convention, not supplied statutory convention. Exact500ft equality unresolved.','sampling':'50ms endpoints; retain full samples.','feasibility_only':False,'scope':'ActualNativeovertakerentry/occupancy comparison; qualifiedtruckreference/500ft retained, no legalverdict'},'measured_values':{'frames':len(history),'duration_s':len(history)/20},'requested_assignments':cfg['variable_assignments'],'requested_variable_assignments':{k:v for k,v in cfg['variable_assignments'].items() if v['kind'] in ('world_setup','controller')},'trace_reference':'trace.jsonl' if history else None,'video_references':videos,'video_frame_map_reference':'video_frames.jsonl' if history else None,'recording_description':cfg['recording_description'],'recording_evidence':[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'} for c in cfg['recording_description']['channels'] if c['name'] in streams]+[{'name':x['name'],'unit':x['unit'],'reference':'context.json#/'+x['name']} for x in cfg['recording_description']['context_inputs'] if (out/'context.json').exists()],'realized_observables':{},'recording_complete':bool(complete and len(history)==900 and len(videos)==len(cameras)+1 and error is None),'restoration':{'restored':bool(restored)},'error':error,'limitations':cfg['recording_description']['limitations']}
  for axis in cfg['case']['sweep_measurements']:
   name=axis['observable'];m=axis['measurement'];hs=[h for h in history if (14<=h['time_s']<=20 if name in ('along_route_body_gap','leader_speed','subject_overall_width','lead_overall_width') else 22<=h['time_s']<=28 if name=='relative_speed' else True)];values=[h['measured_scalars'][name] for h in hs]
   if values:
    stat=m['statistic'];value={'first':lambda x:x[0],'last':lambda x:x[-1],'min':min,'max':max,'mean':lambda x:sum(x)/len(x)}[stat](values)
    result['realized_observables'][name]={'value':value,'unit':axis['unit'],'method':m['method'],'time_window':m['time_window'],'statistic':stat,'sample_window_s':[hs[0]['time_s'],hs[-1]['time_s']],'reference':'channels/'+name+'.jsonl'}
  write(out/'result.json',result)
 return 0 if matched and all(c['matched'] for c in checks) else 2

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output-dir',default=str(ROOT));p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=22100);p.add_argument('--check',action='store_true');args=p.parse_args();cfg=json.loads((ROOT/'config.json').read_text())
 if args.check:print(json.dumps(static(cfg)))
 else:
  for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda n,f:INTERRUPTED.append(n))
  sys.exit(run(cfg,args))
