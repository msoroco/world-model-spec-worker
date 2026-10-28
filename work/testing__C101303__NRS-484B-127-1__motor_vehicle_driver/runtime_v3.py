#!/usr/bin/env python3
"""Original-frame six-step experiment; requested targets never replace telemetry."""
import argparse,copy,hashlib,json,math,pathlib,signal,sys,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parent;DT=.05
from contracts import validate_output,measured_target,summarize,route_contained
from recording import Recording,Resources
from projections import Projection,inside,intersects,gap

def read(p):return json.loads(pathlib.Path(p).read_text())
def write(p,v):pathlib.Path(p).write_text(json.dumps(v,indent=2)+'\n')
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def norm(v):return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def clamp(x,a,b):return max(a,min(b,x))
def heading_error(actual,target):return (target-actual+180)%360-180

def control(x,y,yaw,speed,path,target):
 i=min(range(len(path)),key=lambda n:math.hypot(x-path[n][0],y-path[n][1]));goal=path[min(i+max(3,int(speed*.6)),len(path)-1)]
 angle=math.degrees(math.atan2(goal[1]-y,goal[0]-x));effort=.5*(target-speed)
 return dict(throttle=clamp(effort,0,.8),brake=clamp(-effort,0,1),steer=clamp(heading_error(yaw,angle)/45,-.7,.7))

def physical_gap(a,b,f):return min(p[0]*f[0]+p[1]*f[1] for p in b)-max(p[0]*f[0]+p[1]*f[1] for p in a)

def road_xml(cfg):
 tree=ET.parse(ROOT/'road-template.xodr');root=tree.getroot();root.find('header').set('name',cfg['cell_id']+' authored physical trial');road=root.find('road');road.set('length','2400');road.find('planView/geometry').set('length','2400')
 section=road.find('lanes/laneSection')
 if cfg['mode']=='following':
  left=section.find('left');section.remove(left);right=section.find('right')
  for lane in list(right):
   if lane.get('id')!='-1':right.remove(lane)
  first=right.find('lane');first.find('width').set('a','3.25');first.find('roadMark').set('type','broken');second=copy.deepcopy(first);second.set('id','-2');second.find('roadMark').set('type','solid');right.append(second)
  e=road.find('elevationProfile');e.clear()
  for s,a,b,c,d in [(0,0,.04,0,0),(600,24,.04,-.0001,0),(1000,24,-.04,0,0)]:ET.SubElement(e,'elevation',s=str(s),a=str(a),b=str(b),c=str(c),d=str(d))
 else:
  for side in ('left','right'):
   for lane in section.findall(side+'/lane'):
    if abs(int(lane.get('id')))==1:lane.find('width').set('a','3')
  # Actual adjacent marked access aisle: a 2.5m restricted strip from station600..612.
  # Its white border lines are native OpenDRIVE roadMark geometry, not camera overlays.
  middle=copy.deepcopy(section);middle.set('s','600');end=copy.deepcopy(section);end.set('s','612')
  shoulder=next(l for l in middle.findall('right/lane') if l.get('id')=='-2');shoulder.set('type','restricted');shoulder.find('width').set('a','2.5');mark=shoulder.find('roadMark');mark.set('type','solid');mark.set('color','white');mark.set('width','.2')
  middle.find('right/lane/roadMark').set('type','solid');middle.find('right/lane/roadMark').set('color','white');road.find('lanes').append(middle);road.find('lanes').append(end)
 return ET.tostring(root,encoding='unicode')

def offline_check():
 cfg=read(ROOT/'config.json');proposal=read(ROOT/'proposals/cases.json');assert set(cfg['supported_case_ids'])=={c['case_id'] for c in proposal['cases']};assert proposal['cases'][0]['target_type']=='baseline' and cfg['default_case_id']!=proposal['cases'][0]['case_id']
 assert len(cfg['cameras'])==4 and cfg['capture_hz']==20
 for c in proposal['cases']:
  assert c['recording_description']==cfg['recording_description'];assert all(v['value'] is None for v in c['variable_assignments'].values() if v['kind']=='subject_behavior')
 if cfg['mode'] in ('alley','following'):
  xml=ET.fromstring(road_xml(cfg));assert float(xml.find('road').get('length'))==2400
  if cfg['mode']=='alley':assert xml.find("road/lanes/laneSection[@s='600']/right/lane[@id='-2']").get('type')=='restricted'
  else:assert len(xml.findall("road/lanes/laneSection/right/lane[@type='driving']"))==2
 if cfg['mode'] in ('alley','posted'):
  assert [round(c['variable_assignments']['commanded_approach_speed']['value'],8) for c in proposal['cases'][1:]]==[round((cfg['threshold_mph']+d)*.44704,8) for d in (-5,-.5,5)]
 assert cfg['runtime_requirements'] and all(set(('requirement','category','evidence','next_action','requires_live_execution'))<=set(r) for r in cfg['runtime_requirements'])
 print(json.dumps({'offline_configuration_geometry_cases_and_result_contract':'passed','simulator_connected':False}))

def verify_binding(binding,world,cfg,base):
 """Bind an external native asset by hash, lane geometry, devices and retained proofs."""
 if binding.get('status')!='verified':raise ValueError('Surveyed native scene binding is not verified')
 actual=world.get_map().to_opendrive().encode()
 if hashlib.sha256(actual).hexdigest()!=binding['map_sha256']:raise ValueError('Native scene map hash changed')
 for proof in binding['physical_feature_proofs']:
  source=(base/proof['path']).resolve()
  if not source.is_file() or sha(source)!=proof['sha256']:raise ValueError('Missing/hash-changed physical native feature proof')
 if not binding['physical_feature_proofs']:raise ValueError('Native feature proofs required')
 path=binding['route'];assert len(path)>20
 if any(math.dist(a[:2],b[:2])>4 for a,b in zip(path,path[1:])):raise ValueError('Discontinuous native bound route')
 mapping=world.get_map()
 for p in path:
  wp=mapping.get_waypoint(__import__('carla').Location(x=p[0],y=p[1],z=p[2]),project_to_road=False)
  if wp is None:raise ValueError('Native bound route outside drivable lanes')
 if cfg['mode'] in ('signal','inoperative'):
  governance=binding['device_governance']
  for record in governance:
   actor=world.get_actor(record['actor_id'])
   if actor is None:raise ValueError('Bound governing signal actor missing')
   actual={(w.road_id,w.section_id,w.lane_id) for w in actor.get_stop_waypoints()}
   expected={tuple(lane) for lane in record['lanes']}
   if not expected<=actual:raise ValueError('Native governed signal lane differs from binding')
  if not binding['stop_line'].get('approach_forward_xy'):raise ValueError('Stop-line approach frame missing')
  f=binding['stop_line']['approach_forward_xy']
  if abs(math.hypot(*f)-1)>.001:raise ValueError('Stop-line approach frame is not unit length')
 if cfg['mode']=='signal':
  approach=mapping.get_waypoint(__import__('carla').Location(*path[0][:3]));lanes=[w for w in mapping.generate_waypoints(3) if w.road_id==approach.road_id and str(w.lane_type).endswith('Driving')]
  if any(w.lane_id*approach.lane_id<0 for w in lanes):raise ValueError('Approach is not one-way')
  end=mapping.get_waypoint(__import__('carla').Location(*path[-1][:3]));destination=[w for w in mapping.generate_waypoints(3) if w.road_id==end.road_id and str(w.lane_type).endswith('Driving')]
  if not any(w.lane_id*end.lane_id<0 for w in destination):raise ValueError('Destination is not two-way')
 if cfg['mode']=='posted':
  if binding['speed_sign']['value_mph']!=cfg['threshold_mph']:raise ValueError('Bound posted speed differs from frozen case')
  if not binding.get('governed_polygon'):raise ValueError('Posted particular-portion governance missing')
  if any(abs(w.lane_width-binding['authored_lane_width_m'])>.1 for w in [mapping.get_waypoint(__import__('carla').Location(*p[:3])) for p in path]):raise ValueError('Narrow-road width binding mismatch')
 if cfg['mode']=='inoperative':
  if len(binding.get('peer_routes',[]))<2 or not binding.get('obstruction_props') or not binding.get('stop_line'):raise ValueError('Blind intersection requires stop line, obstructions, earlier-stopped and occupied-vehicle routes')
  if any(not p.get('role') in ('earlier_stopped','intersection_occupying') for p in binding['peer_routes']):raise ValueError('Wrong required peer roles')
  if not binding.get('incoming_lane_extent_m') or min(binding['incoming_lane_extent_m'])<230:raise ValueError('Nine-point search needs230m on every incoming route')
 return True

def spawn_prop(carla,world,spec,owned):
 bp=world.get_blueprint_library().find(spec['blueprint']);tr=carla.Transform(carla.Location(*spec['position_m']),carla.Rotation(yaw=spec.get('yaw_deg',0)));actor=world.spawn_actor(bp,tr);owned.own(actor.destroy)
 return {'actor_id':actor.id,'blueprint':actor.type_id,'position_m':spec['position_m'],'body_vertices_m':[[v.x,v.y,v.z] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]}

def alley_corridor(carla,world,owned):
 """Physical walls using available native collision props; never a 2D annotation."""
 blueprints=world.get_blueprint_library();candidates=[bp for bp in blueprints.filter('static.prop.*') if 'container' in bp.id.lower()]
 if not candidates:raise RuntimeError('external_asset: native collision container mesh required for alley corridor; none found in live inventory')
 bp=sorted(candidates,key=lambda b:b.id)[0];result=[]
 probe=world.spawn_actor(bp,carla.Transform(carla.Location(x=10,y=30,z=1)));owned.own(probe.destroy);e=probe.bounding_box.extent
 if min(e.x,e.y,e.z)<=0:raise RuntimeError('Container collision/body extent unavailable')
 length=2*e.x
 for y in (-6.,7.):
  for x in range(50,2301,max(1,int(length*.95))):result.append(spawn_prop(carla,world,dict(blueprint=bp.id,position_m=[x,y,e.z],yaw_deg=0),owned))
 return result

def validate_histories(trace,participants,footprints,required_ids):
 if len(trace)!=len(participants) or len(trace)!=len(footprints):raise ValueError('Incomplete measured histories')
 for t,p,b in zip(trace,participants,footprints):
  if t['time_s']!=p['time_s'] or t['time_s']!=b['time_s']:raise ValueError('Measured body/participant timestamp mismatch')
  records={r['actor_id']:r for r in p['participants']}
  if not set(required_ids)<=set(records):raise ValueError('Required participant absent')
  for ident in required_ids:
   record=records[ident]
   if any(k not in record for k in ('speed_mps','velocity_mps','position_m','body_vertices_m')) or not record['body_vertices_m']:raise ValueError('Unmeasured participant history')
 return True

def run(args):
 import carla
 # Repository-supplied runtime sources are required by the target environment.
 repo=next((p for p in ROOT.parents if (p/'runtime/python/pipeline_capture.py').is_file()),None)
 if repo:sys.path.insert(0,str(repo/'runtime/python'))
 cfg=read(ROOT/'config.json');case=next(c for c in cfg['cases'] if c['case_id']==(args.case_id or cfg['default_case_id']))
 if case['target_type']=='baseline':raise ValueError('Baseline is unselected definition-only')
 out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
 if (out/'result.json').exists():raise FileExistsError('Preserve earlier original attempt; choose fresh output-dir')
 resources=Resources();actors=Resources();recording=None;stop=[False];world=None;client=None;errors=[];success=False;speeds=[];gaps=[];entries=[];footprints=[];participants=[];history=[];signal_records=[]
 result=dict(case_id=case['case_id'],actor=cfg['actor'],cell_id=cfg['cell_id'],setup_confirmed=False,behavior_attempted=False,maneuver_completed=False,termination_reason='initialization',physical_failure_flags=[],target_checks=[],measured_values={},recording_description=case['recording_description'],recording_evidence=[],realized_observables={},trace_reference=None,video_references=[],video_frame_map_reference=None,requested_variable_assignments={k:v for k,v in case['variable_assignments'].items() if v['kind'] in ('world_setup','controller')})
 for s in (signal.SIGINT,signal.SIGTERM):signal.signal(s,lambda *_:stop.__setitem__(0,True))
 try:
  client=carla.Client(args.host,args.port);client.set_timeout(120)
  if client.get_client_version()!=client.get_server_version():raise RuntimeError('Client/server CARLA version mismatch')
  world=client.get_world();prior_settings=world.get_settings();prior_weather=world.get_weather();prior_name=world.get_map().name;prior_xml=world.get_map().to_opendrive();(out/'previous-world.xodr').write_text(prior_xml)
  state={'world':world,'changed':False}
  def restore_world():
   current=state['world']
   if state['changed']:
    native=next((m for m in client.get_available_maps() if m.rsplit('/',1)[-1]==prior_name.rsplit('/',1)[-1]),None)
    current=client.load_world(native) if native else client.generate_opendrive_world(prior_xml)
   current.apply_settings(prior_settings);current.set_weather(prior_weather)
  resources.own(restore_world)
  if cfg['mode'] in ('alley','following'):
   if any(a.type_id.startswith(('vehicle.','walker.','sensor.')) for a in world.get_actors()):raise RuntimeError('Dedicated lease required: existing actor inventory is not empty')
   world=client.generate_opendrive_world(road_xml(cfg));state['world']=world;state['changed']=True
  settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=DT;settings.no_rendering_mode=False;world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon);mapping=world.get_map()
  binding=None;props=[];signals=[];peers=[];context={'surface':{'material':'authored native dry asphalt','ice_or_snow_installed':False},'participant_lanes':{}}
  if cfg['mode'] in ('posted','signal','inoperative'):
   if not args.binding:raise RuntimeError('external_asset: provide --binding PATH to verified matching native map/physical-feature proof bundle; repository contains no surveyed native inventory')
   binding_path=pathlib.Path(args.binding).resolve();binding=read(binding_path);verify_binding(binding,world,cfg,binding_path.parent);path=binding['route'];context.update({k:binding[k] for k in ('driving_polygons','incoming_topology','intersection_polygon','stop_line','crosswalks','device_governance') if k in binding})
   for k in ('speed_sign','governed_polygon','signal_proof'):
    if k in binding:context[k]=binding[k]
   for spec in binding.get('obstruction_props',[]):props.append(spawn_prop(carla,world,spec,actors))
   signals=[world.get_actor(i) for i in binding.get('signal_actor_ids',[])]
   if cfg['mode'] in ('signal','inoperative') and (not signals or any(s is None for s in signals)):raise RuntimeError('Bound native governing signal actor absent')
   for s in signals:
    old_state=s.get_state();old_frozen=s.is_frozen();resources.own(lambda a=s,v=old_state,f=old_frozen:(a.set_state(v),a.freeze(f)));s.freeze(True)
   if cfg['mode']=='posted':
    sign=world.get_actor(binding['speed_sign']['actor_id'])
    if sign is None or sign.type_id!=binding['speed_sign']['blueprint']:raise ValueError('Bound native speed-sign identity changed')
    expected=binding['speed_sign']['position_m'];actual=sign.get_location()
    if math.dist([actual.x,actual.y,actual.z],expected)>.1:raise ValueError('Bound native speed-sign position changed')
  else:
   station=650 if cfg['mode']=='following' else 300;route=[mapping.get_waypoint_xodr(1,-1,s) for s in range(station,2201,2)]
   if any(w is None for w in route):raise RuntimeError('Authored route discontinuous')
   path=[[w.transform.location.x,w.transform.location.y,w.transform.location.z] for w in route]
   # Derive native-handed surface bounds from the map, not an assumed OpenDRIVE y sign.
   native_centres=[mapping.get_waypoint_xodr(1,lane,station).transform.location.y for lane in ((-1,-2) if cfg['mode']=='following' else (-1,1))]
   width=3.25 if cfg['mode']=='following' else 3.;context['driving_polygons']=[[[0,min(native_centres)-width/2],[2400,min(native_centres)-width/2],[2400,max(native_centres)+width/2],[0,max(native_centres)+width/2]]]
   if cfg['mode']=='alley':props=alley_corridor(carla,world,actors)
   else:
    crest=mapping.get_waypoint_xodr(1,-1,800).transform.location.z
    if not crest>mapping.get_waypoint_xodr(1,-1,650).transform.location.z:raise RuntimeError('Authored hill crest not realized natively')
  # Persist setup before capture so full raw graphs retain authored/physical geometry.
  if binding:
   (out/'native_proofs').mkdir()
   for i,proof in enumerate(binding['physical_feature_proofs']):
    source=(binding_path.parent/proof['path']).resolve();target=out/'native_proofs'/('%03d-'%i+source.name);target.write_bytes(source.read_bytes())
  write(out/'setup-evidence.json',{'map_name':mapping.name,'map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),'bound_native_features':binding,'physical_props':props,'context':context,'requested_case':case})
  p=path[0];yaw=math.degrees(math.atan2(path[1][1]-p[1],path[1][0]-p[0]));ego=world.spawn_actor(world.get_blueprint_library().find('vehicle.tesla.model3'),carla.Transform(carla.Location(x=p[0],y=p[1],z=p[2]+.4),carla.Rotation(yaw=yaw)));actors.own(ego.destroy);context['ego_id']=ego.id
  if cfg['mode']=='following':
   requested=case['variable_assignments']['commanded_following_gap']['value'];wp=mapping.get_waypoint_xodr(1,-1,650+requested+5);tr=wp.transform;tr.location.z+=.4;leader=world.spawn_actor(world.get_blueprint_library().find('vehicle.lincoln.mkz_2020'),tr);actors.own(leader.destroy);context['leader_id']=leader.id;peers.append(dict(actor=leader,path=path,role='leader',speed_mps=8))
  for spec in (binding or {}).get('peer_routes',[]):
   route=spec['route'];p=route[0];yaw=math.degrees(math.atan2(route[1][1]-p[1],route[1][0]-p[0]));actor=world.spawn_actor(world.get_blueprint_library().find(spec.get('blueprint','vehicle.lincoln.mkz_2020')),carla.Transform(carla.Location(x=p[0],y=p[1],z=p[2]+.4),carla.Rotation(yaw=yaw)));actors.own(actor.destroy);peers.append(dict(spec,actor=actor,path=route))
  required_ids=[ego.id]+[p['actor'].id for p in peers]
  contacts=[];sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=ego);actors.own(sensor.destroy);actors.own(sensor.stop);sensor.listen(lambda e:contacts.append(dict(frame=e.frame,other_actor_id=e.other_actor.id)))
  write(out/'config.json',cfg);write(out/'context.json',{'authored_context':case['variable_assignments']['authored_context']['value']})
  recording=Recording(client,ego,out,case['case_id'],case['recording_description'],cfg['cameras'],cfg['required_atoms']);project=Projection(ego.id,cfg['required_atoms'],context)
  history_file=(out/'participant_history.jsonl').open('x');resources.own(history_file.close);body_file=(out/'footprints.jsonl').open('x');resources.own(body_file.close);event_file=(out/'maneuver_events.jsonl').open('x');resources.own(event_file.close)
  start=world.get_snapshot().timestamp.elapsed_seconds;halt_start=None;halt_complete=False;red_blocked=False;left_lamp=False
  result['setup_confirmed']=True;result['behavior_attempted']=True
  for tick in range(round(cfg['duration_s']/DT)):
   elapsed=world.get_snapshot().timestamp.elapsed_seconds-start
   if stop[0]:result['termination_reason']='signal';break
   transform=ego.get_transform();v=norm(ego.get_velocity());target=case['variable_assignments']['commanded_approach_speed']['value'];dynamic=path
   for peer in peers:
    actor=peer['actor'];tr=actor.get_transform();desired=peer.get('speed_mps',8)
    if peer['role']=='earlier_stopped' and elapsed<peer['release_time_s']:
     # The frozen native route contains its actual stop point; the other driver's full halt is observed.
     halt=peer['stop_position_m'];d=math.hypot(tr.location.x-halt[0],tr.location.y-halt[1]);desired=min(desired,math.sqrt(2*1.5*max(0,d-2)))
    c=control(tr.location.x,tr.location.y,tr.rotation.yaw,norm(actor.get_velocity()),peer['path'],desired);actor.apply_control(carla.VehicleControl(**c))
    wp=mapping.get_waypoint(tr.location);context['participant_lanes'][str(actor.id)]={'road_id':wp.road_id,'lane_id':wp.lane_id,'s':wp.s}
   if cfg['mode']=='following':
    leader=peers[0]['actor'];tr=leader.get_transform();f=transform.get_forward_vector();a=[[p.x,p.y,p.z] for p in ego.bounding_box.get_world_vertices(transform)];b=[[p.x,p.y,p.z] for p in leader.bounding_box.get_world_vertices(tr)];observed=physical_gap(a,b,[f.x,f.y]);desired=case['variable_assignments']['commanded_following_gap']['value'];target=clamp(8+.15*(observed-desired),0,15)
    # Native waypoint next-lane centres determine the lateral sign; no handedness assumption.
    source=mapping.get_waypoint_xodr(1,-1,800).transform.location;dest=mapping.get_waypoint_xodr(1,-2,800).transform.location;blend=clamp((elapsed-15)/6,0,1);shift=(dest.y-source.y)*(blend*blend*(3-2*blend));dynamic=[[p[0],p[1]+shift,p[2]] for p in path]
   if signals:
    phase=carla.TrafficLightState.Off if cfg['mode']=='inoperative' else carla.TrafficLightState.Yellow if elapsed<4 else carla.TrafficLightState.Red
    for light in signals:light.set_state(phase)
    stop_point=binding['stop_line']['reference_position_m'];d=math.hypot(transform.location.x-stop_point[0],transform.location.y-stop_point[1]);halt=case['variable_assignments'].get('commanded_halt',{}).get('value',False)
    if halt and not halt_complete:
     target=min(target,math.sqrt(2*1.5*max(0,d-4)))
     if d<6 and v<.05:
      halt_start=elapsed if halt_start is None else halt_start
      if elapsed-halt_start>=1:halt_complete=True
    if cfg['mode']=='signal' and case['variable_assignments']['obey_red']['value'] and elapsed>=4:target=min(target,math.sqrt(2*1.5*max(0,d-4)));red_blocked=True
   if elapsed<1 or elapsed>=cfg['duration_s']-5:target=0
   ego.apply_control(carla.VehicleControl(**control(transform.location.x,transform.location.y,transform.rotation.yaw,v,dynamic,target)))
   left_lamp=cfg['mode']=='following' and 13<=elapsed<=22;ego.set_light_state(carla.VehicleLightState.LeftBlinker if left_lamp else carla.VehicleLightState.NONE)
   frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds-start;row=recording.tick(frame,time_s,project,extra={'ego_lamp_bits':int(ego.get_light_state())});last=project.last
   speeds.append({'time_s':time_s,'value':row['speed_mps']})
   if cfg['mode']=='following':gaps.append({'time_s':time_s,'value':last['values']['rel.surface_gap']})
   history_file.write(json.dumps({'time_s':time_s,'participants':last['participants']})+'\n');body_file.write(json.dumps({'time_s':time_s,'vertices':last['ego_vertices']})+'\n');event_file.write(json.dumps({'time_s':time_s,'entries':last['entries'],'stops':last['stops'],'signals':last['values'].get('dev.traffic_signal',[]),'halt_controller_completed':halt_complete})+'\n');history.append(last)
   if not last['occupancy']['whole_body_contained']:result['termination_reason']='roadway_departure';break
   if contacts:result['termination_reason']='collision';break
   if abs(ego.get_transform().rotation.roll)>30:result['termination_reason']='loss_of_control';break
  else:result['maneuver_completed']=True;result['termination_reason']='frozen_episode_completed'
  mean,window=summarize(speeds,*cfg['measurement_window_s']);result['measured_values']['ego_speed_mps']=mean
  if cfg['mode'] in ('alley','posted'):
   requested=case['variable_assignments']['commanded_approach_speed']['value'];result['target_checks'].append(measured_target('commanded_approach_speed',requested,mean,.5*.44704,'native velocity norm; original-time mean','channels/kin.speed.jsonl'))
   result['realized_observables']['ego_speed']={'value':mean,'unit':'m/s','method':'native velocity norm','time_window':cfg['measurement_window_s'],'statistic':'mean','sample_window_s':window,'reference':'channels/kin.speed.jsonl'}
  if cfg['mode']=='following':
   measured,window=summarize(gaps,5,14);result['measured_values']['following_gap_m']=measured;result['target_checks'].append(measured_target('commanded_following_gap',case['variable_assignments']['commanded_following_gap']['value'],measured,2,'body-front-to-rear projected longitudinal gap 5..14s','participant_history.jsonl'))
   final=mapping.get_waypoint(ego.get_location());result['target_checks'].append(measured_target('completed_lane_change',-2,final.lane_id,0,'native final lane_id plus full body containment',['participant_history.jsonl','footprints.jsonl']))
  if cfg['mode']=='signal':
   entry=project.first_entries.get(ego.id);entered=bool(entry and any(h['time_s']==entry['time_s'] and any(d.get('state')=='Red' for d in h['values'].get('dev.traffic_signal',[])) for h in history));requested=not case['variable_assignments']['obey_red']['value'];result['target_checks'].append(measured_target('red_entry_branch',requested,entered,0,'first whole-body intersection overlap against observed red exhibition','maneuver_events.jsonl'))
  if cfg['mode']=='inoperative':
   stop_event=project.stop_events.get(ego.id);entry=project.first_entries.get(ego.id);forward=binding['stop_line']['approach_forward_xy'];reference=binding['stop_line']['reference_position_m'];before_line=bool(stop_event and all((v[0]-reference[0])*forward[0]+(v[1]-reference[1])*forward[1]<=0 for v in stop_event['body_vertices_m']));halt_before=bool(stop_event and entry and stop_event['time_s']<entry['time_s'] and halt_complete and before_line);result['target_checks'].append(measured_target('commanded_halt',case['variable_assignments']['commanded_halt']['value'],halt_before,0,'observed cessation bracket before footprint intersection entry; controller full-halt episode','maneuver_events.jsonl'))
   roles={p['role']:p['actor'].id for p in peers};earlier=roles['earlier_stopped'];occupant=roles['intersection_occupying'];result['target_checks'].append(measured_target('entered_intersection',True,ego.id in project.first_entries,0,'observed full-body overlap with bound native intersection','maneuver_events.jsonl'));all_off=all(h['values']['dev.inoperative']['all_indications_off'] for h in history);result['target_checks'].append(measured_target('all_native_heads_off',True,all_off,0,'every original native signal indication throughout entry episode','channels/dev.inoperative.jsonl'));result['target_checks'].append(measured_target('required_peer_histories',True,earlier in project.stop_events and occupant in project.first_entries,0,'retained full original vehicle stop/occupancy histories','participant_history.jsonl'))
  positions=[next(a['position_m'] for a in p['participants'] if a['actor_id']==ego.id) for p in history];travelled=sum(math.dist(a,b) for a,b in zip(positions,positions[1:]));result['target_checks'].append(measured_target('actual_approach_movement',True,travelled>.5,0,'original native trajectory displacement;0.5m is an engineering movement criterion','trace.jsonl'))
  result['target_checks'].append(measured_target('frozen_episode_complete',True,result['maneuver_completed'],0,'original frame count and termination reason',['trace.jsonl','footprints.jsonl']))
  result.update(required_participant_ids=required_ids,participant_history_reference='participant_history.jsonl',footprint_reference='footprints.jsonl',driving_polygons=context['driving_polygons'])
  if not result['maneuver_completed']:result['physical_failure_flags'].append(result['termination_reason'])
 except BaseException as exc:result['physical_failure_flags'].append(type(exc).__name__+': '+str(exc));result['termination_reason']='construction_capture_or_target_failure'
 finally:
  if recording:errors+=recording.close();result.update(recording.result_fields());result['recording_evidence'].append({'name':'authored_context','unit':'object','reference':'context.json'})
  # All cleanup paths are independent: a failed encoder cannot suppress actor/settings restoration.
  errors+=actors.close();errors+=resources.close();result['restoration']={'restored':not errors,'errors':errors};result['physical_failure_flags']+=errors
  if recording and not result['physical_failure_flags']:
   try:
    validate_output(out,result,cfg['recording_description'])
    loadrows=lambda path:[json.loads(line) for line in path.read_text().splitlines() if line]
    validate_histories(loadrows(out/'trace.jsonl'),loadrows(out/'participant_history.jsonl'),loadrows(out/'footprints.jsonl'),result['required_participant_ids']);success=True
   except BaseException as exc:result['physical_failure_flags'].append('result_contract: '+str(exc))
  write(out/'result.json',result)
 return 0 if success else 2

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000);p.add_argument('--case-id');p.add_argument('--binding',help='Verified native scene feature/proof bundle for device-dependent cases');a=p.parse_args()
 if a.check:offline_check()
 elif not a.output_dir:p.error('--output-dir required')
 else:sys.exit(run(a))
