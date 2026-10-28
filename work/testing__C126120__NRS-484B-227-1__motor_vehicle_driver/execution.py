"""Executable assignment-specific setup, controller, observation and finalization.

No legal classifier lives here. Every reported outcome comes from the retained
original frame; authored administrative assumptions are separately identified.
"""
import json,math,os,signal,sys,xml.etree.ElementTree as ET
from pathlib import Path
from recording import Recording,Resources
from contracts import validate_output,measured_target,summarize

class CapabilityError(RuntimeError):pass

def finite(value):
    if not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Nonfinite physical value')
    return value

def xy(vertex):return [float(vertex.x),float(vertex.y)]

def hull(vertices):
    points=sorted(set(tuple(p[:2]) for p in vertices))
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower=[];upper=[]
    for p in points:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1]+upper[:-1]]

def intersects(a,b):
    if len(a)<3 or len(b)<3:raise ValueError('Convex polygon required')
    for poly in (a,b):
        for p,q in zip(poly,poly[1:]+poly[:1]):
            axis=[p[1]-q[1],q[0]-p[0]];pa=[sum(v[i]*axis[i] for i in (0,1)) for v in a];pb=[sum(v[i]*axis[i] for i in (0,1)) for v in b]
            if max(pa)<min(pb) or max(pb)<min(pa):return False
    return True

def route_points(mapping,sections):
    points=[]
    for road,lane,start,end in sections:
        steps=max(1,int(abs(end-start)/1.))
        for i in range(steps+1):
            station=start+(end-start)*i/steps;wp=mapping.get_waypoint_xodr(road,lane,station)
            if wp is None:raise CapabilityError('Missing native route station '+str((road,lane,station)))
            if points and wp.transform.location.distance(points[-1].transform.location)>.0 and wp.transform.location.distance(points[-1].transform.location)>2.:raise CapabilityError('Native route discontinuity')
            points.append(wp)
    return points

def native_surface(mapping):
    # Exact recorded native waypoint width patches, not controller-target envelope.
    polygons=[]
    for wp in mapping.generate_waypoints(.5):
        loc=wp.transform.location;f=wp.transform.get_forward_vector();r=wp.transform.get_right_vector();half=wp.lane_width/2
        polygons.append([[loc.x+sign*.55*f.x+side*half*r.x,loc.y+sign*.55*f.y+side*half*r.y] for sign,side in [(-1,-1),(1,-1),(1,1),(-1,1)]])
    if not polygons:raise CapabilityError('Native driving surface unavailable')
    return polygons

def spawn(world,resources,blueprint,transform):
    bp=world.get_blueprint_library().find(blueprint);actor=world.try_spawn_actor(bp,transform)
    if actor is None:raise CapabilityError('Spawn failed '+blueprint)
    resources.own(actor.destroy);return actor

def divider(world,resources,intervals,opening):
    """Place actual barrier actors outside the frozen opening; retain their bodies."""
    import carla
    available=sorted([bp.id for bp in world.get_blueprint_library().filter('static.prop.*') if any(word in bp.id for word in ('concretebarrier','streetbarrier','roadbarrier'))])
    if not available:raise CapabilityError('External asset: concrete/street/road barrier blueprint unavailable')
    blueprint=available[0];actors=[]
    for begin,end in intervals:
        x=begin
        while x<end:
            actor=spawn(world,resources,blueprint,carla.Transform(carla.Location(x=x,y=-10,z=.15)))
            if hasattr(actor,'set_simulate_physics'):actor.set_simulate_physics(False)
            vertices=[xy(v) for v in actor.bounding_box.get_world_vertices(actor.get_transform())];polygon=hull(vertices)
            if not polygon:raise CapabilityError('Barrier has no measured body')
            # Gaps are forbidden; use measured body length with a 0.1m overlap.
            length=max(v[0] for v in polygon)-min(v[0] for v in polygon)
            if length<.2:raise CapabilityError('Unsuitable barrier body length')
            if min(v[0] for v in polygon)<opening[1] and max(v[0] for v in polygon)>opening[0]:raise CapabilityError('Measured barrier intrudes into opening')
            actors.append(actor);x+=length-.1
    return actors

def body(actor):
    t=actor.get_transform();v=actor.get_velocity()
    return {'actor_id':actor.id,'position_m':[t.location.x,t.location.y,t.location.z],'heading_deg':t.rotation.yaw,'velocity_mps':[v.x,v.y,v.z],'speed_mps':math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z),'vertices':[[p.x,p.y,p.z] for p in actor.bounding_box.get_world_vertices(t)]}

def evidence_devices(world):
    records=[]
    for actor in world.get_actors():
        if not actor.type_id.startswith('traffic.'):continue
        record={'actor_id':actor.id,'blueprint':actor.type_id,'position_m':list(xy(actor.get_location()))}
        if hasattr(actor,'get_state'):record['state']=str(actor.get_state())
        if hasattr(actor,'get_affected_lane_waypoints'):record['governed_lanes']=[[wp.road_id,wp.section_id,wp.lane_id] for wp in actor.get_affected_lane_waypoints()]
        records.append(record)
    return records

def snapshot(world,ego,others,time_s,region,history,geometry):
    participants=[body(a) for a in [ego]+others];subject=participants[0];wp=world.get_map().get_waypoint(ego.get_location(),project_to_road=False)
    if wp is None:raise CapabilityError('Subject departed native driving surface')
    forward=wp.transform.get_forward_vector();weather=world.get_weather();lights=int(ego.get_light_state())
    current={'time_s':time_s,'participants':participants,'ego':subject,'devices':evidence_devices(world),'weather':{k:getattr(weather,k) for k in ('precipitation','wetness','fog_density','fog_distance','precipitation_deposits')},'road':{'road_id':wp.road_id,'lane_id':wp.lane_id,'lane_width_m':wp.lane_width,'station_m':wp.s,'forward':[forward.x,forward.y]},'lamps':lights,'applied_controls':[{'actor_id':a.id,'throttle':a.get_control().throttle,'brake':a.get_control().brake} for a in [ego]+others],'physical_dividers':geometry['physical_dividers']}
    current['inside']=[intersects(hull(p['vertices']),region) for p in participants] if region else [False for p in participants]
    current['distance_m']=history[-1]['distance_m']+math.dist(history[-1]['ego']['position_m'],subject['position_m']) if history else 0.
    return current

def project(atom,sample,history,geometry):
    """Value-free raw projections. Qualitative atoms retain raw arguments only."""
    if not all(key in sample for key in ('ego','participants','road','weather')) or 'intersection' not in geometry:raise CapabilityError('Required raw projection sample unavailable')
    ego=sample['ego'];others=sample['participants'][1:];road=sample['road'];weather=sample['weather'];region=geometry['intersection']
    positions=[{'actor_id':p['actor_id'],'position_m':p['position_m'],'velocity_mps':p['velocity_mps'],'footprint':hull(p['vertices'])} for p in sample['participants']]
    if atom=='kin.speed':return ego['speed_mps']
    if atom=='kin.heading':return ego['heading_deg']
    if atom=='kin.velocity':return [{'actor_id':p['actor_id'],'velocity_mps':p['velocity_mps']} for p in sample['participants']]
    if atom=='kin.path_length':return sample['distance_m']
    if atom=='sig.turn_indicator':return {'ego_lamp_bits':sample['lamps'],'original_RGB_reference':'camera-1.webm','interpretation':'API bits and optical recording separate'}
    if atom=='sig.hand_signal':return {'capture_method':'original side RGB camera; no hand-signal controller or interpretation','video':'camera-1.webm','frame_time_s':sample['time_s']}
    if atom=='drv.distance_while':return {'actual_distance_m':sample['distance_m'],'ego_lamp_bits':sample['lamps'],'course_heading_deg':ego['heading_deg'],'finalizer':'signal_summary.json'}
    if atom=='st.intersection':return {'boundary_m':region,'method':'connected roadway boundary intersection; separate 20m-spaced crossing','native_road_ids':geometry['intersection_road_ids']}
    if atom=='st.lane_enters':return {'intersection_boundary_m':region,'participants':positions,'native_road_routes':geometry['participant_routes']}
    if atom in ('drv.entering_intersection','drv.in_intersection'):return [{'actor_id':p['actor_id'],'footprint_intersects_boundary':inside,'region':region} for p,inside in zip(sample['participants'],sample['inside'])]
    if atom=='drv.arrival_order':return {'current_occupancy':[{'actor_id':p['actor_id'],'inside':v} for p,v in zip(sample['participants'],sample['inside'])],'original_time_s':sample['time_s'],'event_convention':'first footprint intersection, retain adjacent-sample brackets'}
    if atom=='drv.approaching':return {'subject_position_m':ego['position_m'],'subject_velocity_mps':ego['velocity_mps'],'boundary_m':region}
    if atom=='drv.yields_to':return {'participants':positions,'region':region,'phase':'raw precedence trajectories; no subjective or safety cutoff','occupancy':sample['inside']}
    if atom.startswith('dev.'):
        kinds={'dev.traffic_signal':'traffic_light','dev.stop_sign':'stop','dev.yield_sign':'yield','dev.regulatory_sign':'one'}
        return {'inventory':[d for d in sample['devices'] if kinds.get(atom,'') in d['blueprint']],'inventory_method':'all original-frame native traffic actors; authored map has no omitted fabricated controls'}
    if atom in ('drv.turning','drv.u_turn','drv.lane_change'):return {'position_m':ego['position_m'],'heading_deg':ego['heading_deg'],'native_lane':road,'start_heading_deg':history[0]['ego']['heading_deg'] if history else ego['heading_deg'],'interpretation':'original trajectory; maneuver outcome finalized separately'}
    if atom in ('rel.oncoming','rel.bearing'):return {'positions_velocities':positions,'method':'original world vectors; no guessed relative label'}
    if atom in ('st.median_or_divider','st.one_way_roadway'):return {'physical_divider_actors':sample['physical_dividers'],'native_road':road,'authored_context':geometry['authored_context']}
    if atom in ('st.lane_direction','drv.wrong_way'):return {'native_forward':road['forward'],'actual_velocity_mps':ego['velocity_mps'],'dot_product_mps':sum(a*b for a,b in zip(road['forward'],ego['velocity_mps'][:2])),'road_id':road['road_id'],'lane_id':road['lane_id']}
    if atom=='rel.occupies':return {'footprint_m':hull(ego['vertices']),'road':road,'divider_polygons':[d['footprint_m'] for d in sample['physical_dividers']]}
    if atom=='drv.queue_behind':return {'participants':positions,'native_road':road,'method':'unclassified actual participant geometry; no safe-gap rule'}
    if atom=='st.lane_width':return road['lane_width_m']
    if atom=='st.roadway':return {'native_road':road,'surface_source':'road.xodr','surface_geometry':geometry['surface_reference'],'footprint_m':hull(ego['vertices'])}
    if atom=='st.curvature':return {'road_id':road['road_id'],'station_m':road['station_m'],'authored_opendrive':'road.xodr','native_heading_deg':ego['heading_deg']}
    if atom in ('env.wet_road','env.ice_or_snow','env.precipitation','env.visibility'):return {'native_weather':weather,'authored_surface':geometry['surface_provenance'],'original_RGB':'camera-0.webm','interpretation':'raw world and RGB evidence; no weather setting is claimed as measured atmospheric visibility or ice detection'}
    if atom=='drv.sight_distance_adequate':return {'subject':positions[0],'native_route':road,'original_RGB':'camera-0.webm','criterion':'unresolved; no adequacy cutoff','ray_measurement_reference':'capture/evidence.jsonl'}
    if atom=='drv.stopping_distance':return {'phase':sample.get('braking_phase','approach'),'position_m':ego['position_m'],'actual_speed_mps':ego['speed_mps'],'actual_path_m':sample['distance_m'],'control_reference':'trace.jsonl','finalizer':'stopping_summary.json'}
    raise CapabilityError('No truthful mandatory projection implemented for '+atom)

def event_summary(samples):
    entries={};exits={}
    for previous,current in zip(samples,samples[1:]):
        for i,p in enumerate(current['participants']):
            ident=str(p['actor_id'])
            if not previous['inside'][i] and current['inside'][i] and ident not in entries:entries[ident]=[previous['time_s'],current['time_s']]
            if previous['inside'][i] and not current['inside'][i]:exits[ident]=[previous['time_s'],current['time_s']]
    return {'entry_brackets_s':entries,'exit_brackets_s':exits,'method':'full convex footprint first intersection, adjacent-original-frame uncertainty'}

def command(actor,target,point,reverse=False):
    import carla
    t=actor.get_transform();v=actor.get_velocity();speed=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z);error=target-speed
    desired=math.atan2(point[1]-t.location.y,point[0]-t.location.x);heading=math.radians(t.rotation.yaw)+(math.pi if reverse else 0)
    angle=(desired-heading+math.pi)%(2*math.pi)-math.pi
    actor.apply_control(carla.VehicleControl(throttle=min(.7,max(0.,error*.35)),brake=min(1.,max(0.,-error*.5)),steer=max(-.65,min(.65,angle*( -1.4 if reverse else 1.4))),reverse=reverse))

def materialize_sweep(config,index):
    if index is None:return next(c for c in config['cases'] if c['case_id']==config['selected_case_id'])
    law=config['law_id'];values=[-2.,-1.,0.,1.,2.] if law.endswith('250-2') else [0.,1.,2.,3.,4.] if law.endswith('250-1') else [4.,6.,8.,10.,12.]
    if not 0<=index<len(values):raise ValueError('Frozen sweep index outside 0..4')
    case=json.loads(json.dumps(config['cases'][0]));case['case_id']=config['assignment_id']+'__physical_sweep_'+str(index);case['target_type']='judgment_sweep';case['target_law_id']=law
    if law.endswith(('250-1','250-2')):case['variable_assignments']['commanded_release_offset_s']={'kind':'controller','value':values[index],'unit':'s'}
    elif law.endswith('600-1a'):case['variable_assignments']['commanded_approach_speed']['value']=values[index]
    else:raise ValueError('No physical judgment sweep for this law')
    return case

def runtime_path(root):
    paths=[Path(os.environ['SCENARIO_RUNTIME_PYTHON'])] if os.environ.get('SCENARIO_RUNTIME_PYTHON') else []
    paths += [p/'runtime/python' for p in [root]+list(root.parents)]
    for path in paths:
        if (path/'pipeline_capture.py').is_file():sys.path.insert(0,str(path));return
    try:__import__('pipeline_capture')
    except ImportError:raise CapabilityError('Supplied runtime/python must be on PYTHONPATH or SCENARIO_RUNTIME_PYTHON')

def build_setup(client,resources,cfg,case,out):
    import carla
    law=cfg['law_id'];world=client.get_world();native=law.endswith(('220-1','413-2'))
    if law.endswith(('250-1','250-2')):
        from crossing import build_crossing
        source=build_crossing();routes=[[(1,-1,150.,189.5),(11,-1,.0,20.),(2,-1,.0,65.)],[(5,-1,180.,192.5),(12,-1,0.,7.),(6,-1,0.,18.)]]
        region=[[200,0],[207,0],[207,7],[200,7]];median_intervals=[(20,180),(220,400)];opening=[190,210]
    elif law.endswith('227-1'):
        from maneuvers import build_uturn
        source=build_uturn();routes=[[(1,-1,100.,199.5),(2,-1,0.,math.pi*10-.1),(3,-1,0.,100.)]]
        region=[];median_intervals=[(20,175),(240,400)];opening=[185,235]
    elif law.endswith('600-1a'):
        from geometry import build_road
        source=build_road(length=1000.);routes=[[(1,-1,270.,900.)],[(1,-2,310.,940.)]];region=[];median_intervals=[];opening=[]
    elif native:
        source=None;routes=[];region=[];median_intervals=[];opening=[]
    else:raise CapabilityError('Unsupported exact law')
    if source is not None:
        world=client.generate_opendrive_world(source,carla.OpendriveGenerationParameters(vertex_distance=.5,max_road_length=50.,wall_height=0.,additional_width=0.,smooth_junctions=False,enable_mesh_visibility=True))
    settings=world.get_settings();resources.own(lambda:world.apply_settings(settings));changed=world.get_settings();changed.synchronous_mode=True;changed.fixed_delta_seconds=.05;world.apply_settings(changed)
    mapping=world.get_map();paths=[];barriers=[]
    if native:
        if law.endswith('220-1'):
            from one_way import native_binding
            binding=native_binding(world,case['variable_assignments']['test_branch']['value'])
        else:
            binding=cfg.get('native_business_binding')
            if not binding:raise CapabilityError('External asset/context: no source-verified native business-district frontage and designated freight loading-zone binding supplied; statutory business definition absent from inputs/definitions.jsonl')
            if not binding.get('frontage_evidence') or not binding.get('loading_zone_evidence'):raise CapabilityError('External business/loading-zone evidence missing')
        if mapping.name!=binding['map']:raise CapabilityError('Native map identity mismatch; do not replace devices with authored OpenDRIVE')
        points=binding['route'];paths=[points];t=binding['spawn'];ego=spawn(world,resources,binding['blueprint'],carla.Transform(carla.Location(**t['location']),carla.Rotation(**t['rotation'])));others=[]
        authored={'native_binding':binding,'administrative_facts':'explicit authored context with source evidence; not derived from props'}
    else:
        waypoints=[route_points(mapping,r) for r in routes]
        paths=[[[wp.transform.location.x,wp.transform.location.y] for wp in route] for route in waypoints]
        def actor_at(wp):
            t=wp.transform;t.location.z+=.4;return spawn(world,resources,'vehicle.tesla.model3',t)
        ego=actor_at(waypoints[0][0]);others=[actor_at(wp[0]) for wp in waypoints[1:]]
        if median_intervals:barriers=divider(world,resources,median_intervals,opening)
        branch=case['variable_assignments']['test_branch']['value']
        if law.endswith('227-1') and branch=='u_turn_divider':
            # Same physical road/median and controller; only requested crossing path
            # shifts into the intact physical divider. Collisions are preserved.
            paths[0]=[[x-60 if x>150 or y<0 else x,y] for x,y in paths[0]]
        if law.endswith('227-1') and 'multiple' in branch:
            n=len(paths[0])//2;paths[0]=paths[0][:n]+list(reversed(paths[0][n-10:n]))+paths[0][n-10:]
        authored={'highway_identities':['main_highway','crossing_highway'] if region else ['main_highway'],'public_dedication_access':'authored test assumption; not simulator-measured','vehicle_driver_scope':'conventional vehicle physically controlled by controller','opening_x_m':opening,'separate_roadway_crossings':True if region else False}
    # Native maps/explicit generated lane widths are saved before capture.
    polygons=native_surface(mapping);physical=[{'actor_id':a.id,'blueprint':a.type_id,'footprint_m':hull([xy(v) for v in a.bounding_box.get_world_vertices(a.get_transform())]),'transform':str(a.get_transform())} for a in barriers]
    geometry={'intersection':region,'intersection_road_ids':[11,12] if region else [],'participant_routes':routes or paths,'physical_dividers':physical,'authored_context':authored,'surface_reference':'road.xodr','surface_provenance':{'authored_surface':'native generated asphalt roads' if source else 'native map surfaces','ice_or_snow':'no ice/snow meshes authored in generated world' if source else 'native surface inventory requires recorded source','map_identity':mapping.name},'driving_polygons':polygons}
    (out/'authored_geometry.json').write_text(json.dumps(geometry,indent=2));(out/'context.json').write_text(json.dumps({'witness_context':dict(authored=authored,exact_requirements=cfg['witness_requirements'])},indent=2))
    collision=[]
    sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=ego);resources.own(sensor.destroy);resources.own(sensor.stop);sensor.listen(lambda event:collision.append({'frame':event.frame,'other_actor_id':event.other_actor.id}))
    return world,ego,others,paths,geometry,collision

def execute(args,config,case,root):
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True);resources=Resources();recording=None;samples=[];footprints=[];speeds=[];stopped=[False];result={'case_id':case['case_id'],'requested_variable_assignments':case['variable_assignments'],'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'physical_failure_flags':[],'termination_reason':'preflight','measured_values':{},'target_checks':[],'recording_description':case['recording_description'],'recording_evidence':[],'realized_observables':{},'runtime_uncertainties':config['runtime_uncertainties']}
    prior={s:signal.signal(s,lambda *unused:stopped.__setitem__(0,True)) for s in (signal.SIGINT,signal.SIGTERM)}
    try:
        capture_names=['trace.jsonl','authored_geometry.json','context.json','participants.jsonl','footprint.jsonl','ego_speed.jsonl','capture','channels']+['camera-'+str(i)+'.webm' for i in range(4)]
        if any((out/name).exists() for name in capture_names):raise CapabilityError('Existing capture/evidence would be overwritten; use a new capture output directory')
        runtime_path(root);import carla
        client=carla.Client(args.host,args.port);client.set_timeout(40.)
        if client.get_client_version()!=client.get_server_version():raise CapabilityError('Client/server version mismatch')
        world,ego,others,paths,geometry,collisions=build_setup(client,resources,config,case,out)
        (out/'config.json').write_text(json.dumps(config,indent=2));recording=Recording(client,ego,out,case['case_id'],case['recording_description'],config['cameras'],config['required_atoms']);resources.own(recording.close)
        optical_samples=[];optical_tap=None;lamp_camera=None
        if config['law_id'].endswith('413-2'):
            cameras=[a for a in world.get_actors() if a.type_id=='sensor.camera.rgb' and getattr(getattr(a,'parent',None),'id',None)==ego.id]
            cameras.sort(key=lambda a:a.id);lamp_camera=cameras[1]
            optical_tap=OpticalTap(recording.encoders[1].stdin,config['cameras'][1]['width'],config['cameras'][1]['height'],optical_samples);recording.encoders[1].stdin=optical_tap
        result['setup_confirmed']=True;indices=[0 for _ in paths];other_entered=False;law=config['law_id'];branch=case['variable_assignments']['test_branch']['value'];start_time=None;braking_start=None;control_target=case['variable_assignments']['commanded_approach_speed']['value']
        history_file=(out/'participants.jsonl').open('x');resources.own(history_file.close);body_file=(out/'footprint.jsonl').open('x');resources.own(body_file.close)
        for step in range(int(config.get('timeout_s',90.)/.05)):
            if stopped[0]:result['termination_reason']='termination_signal';break
            elapsed=step*.05
            current_ego=body(ego);other_inside=bool(others and intersects(hull(body(others[0])['vertices']),geometry['intersection'])) if geometry['intersection'] else False
            other_entered=other_entered or other_inside
            for i,actor in enumerate([ego]+others):
                position=actor.get_location();path=paths[i]
                while indices[i]<len(path)-1 and math.dist([position.x,position.y],path[indices[i]])<2.5:indices[i]+=1
                target=control_target if i==0 else 3. if law.endswith(('250-1','250-2')) else control_target
                if law.endswith('250-1') and i==0 and branch=='prior_entry_yield' and other_inside and other_entered:target=0.
                if law.endswith(('250-1','250-2')):
                    offset=case['variable_assignments'].get('commanded_release_offset_s',{'value':0.})['value'];delay=max(0.,offset) if i==0 else max(0.,-offset)
                    if elapsed<delay:target=0.
                if law.endswith('600-1a') and i==0 and position.x>=650:
                    target=0.
                    if braking_start is None:braking_start=len(samples)
                reverse=False
                if law.endswith('227-1') and 'multiple' in branch:
                    dx=path[indices[i]][0]-position.x;dy=path[indices[i]][1]-position.y;f=actor.get_transform().get_forward_vector();reverse=dx*f.x+dy*f.y<-.2
                command(actor,target,path[indices[i]],reverse)
                if law.endswith('413-2') and i==0:
                    from signaling import requested_signal
                    remaining=max(0.,config['turn_onset_station_m']-sum(math.dist(a,b) for a,b in zip(path[:indices[i]],path[1:indices[i]+1])))
                    actor.set_light_state(carla.VehicleLightState.RightBlinker if requested_signal(remaining,case['variable_assignments']['commanded_signal_distance']['value']) else carla.VehicleLightState.NONE)
            frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds
            if start_time is None:start_time=time_s
            sample=snapshot(world,ego,others,time_s,geometry['intersection'],samples,geometry);sample['braking_phase']='braking' if braking_start is not None else 'approach'
            def observations(row,event):
                values={channel['name']:project(channel['name'],sample,samples,geometry) for channel in case['recording_description']['channels']}
                if 'drv.sight_distance_adequate' in values:
                    visibility=event.get('visibility')
                    if not visibility:raise CapabilityError('Required original any-body sight horizons unavailable')
                    values['drv.sight_distance_adequate']['raw_visibility']=visibility
                return values
            if optical_tap is not None:optical_tap.context={'time_s':time_s,'carla_frame':frame,'roi':rear_body_roi(lamp_camera,ego,optical_tap.width,optical_tap.height)}
            row=recording.tick(frame,time_s,observations,extra={'requested_target_speed_mps':control_target,'phase':sample['braking_phase']});samples.append(sample)
            history_file.write(json.dumps({'time_s':time_s,'participants':sample['participants'],'applied_controls':sample['applied_controls']})+'\n');body_file.write(json.dumps({'time_s':time_s,'vertices':sample['ego']['vertices']})+'\n');speeds.append({'time_s':time_s,'value':row['speed_mps']});result['behavior_attempted']=True
            if collisions:result['physical_failure_flags'].append('recorded_collision');result['termination_reason']='collision';break
            completion=(sample['ego']['speed_mps']<.15 and braking_start is not None and len(samples)>braking_start+5) if law.endswith('600-1a') else indices[0]==len(paths[0])-1 and math.dist(sample['ego']['position_m'][:2],paths[0][-1])<3.
            if completion:result['maneuver_completed']=True;result['termination_reason']='physical_maneuver_complete';break
        else:result['termination_reason']='engineering_timeout'
        result.update(recording.result_fields());result['recording_evidence'].append({'name':'witness_context','unit':'structured','reference':'context.json'});result['required_participant_ids']=[a.id for a in [ego]+others];result['participant_history_reference']='participants.jsonl';result['footprint_reference']='footprint.jsonl';result['driving_polygons']=geometry['driving_polygons'];result['collision_evidence']=collisions
        if not samples:raise CapabilityError('No original samples')
        with (out/'ego_speed.jsonl').open('x') as stream:
            for s in speeds:stream.write(json.dumps(s)+'\n')
        # Speed achievement is engineering tracking, not a legal tolerance.
        approach=[s for s,sample in zip(speeds,samples) if sample['braking_phase']=='approach' and s['time_s']>=samples[0]['time_s']+5]
        if not approach:raise CapabilityError('No steady-approach measurement window')
        start=max(approach[0]['time_s'],approach[-1]['time_s']-5);mean,window=summarize(approach,start,approach[-1]['time_s'])
        result['realized_observables']['ego_speed']={'value':mean,'unit':'m/s','method':'original velocity-norm final up-to-5s approach mean','time_window':'actual sample window before braking','statistic':'mean','sample_window_s':window,'reference':'ego_speed.jsonl'}
        if law.endswith(('600-1a','220-1','413-2')):result['target_checks'].append(measured_target('approach_speed',control_target,mean,.22352,'actual velocity norm, engineering 0.5mph tolerance',['ego_speed.jsonl','road.xodr']))
        if law.endswith(('250-1','250-2')):
            summary=event_summary(samples);(out/'arrival_summary.json').write_text(json.dumps(summary,indent=2));result['measured_values']['arrival']=summary;entries=summary['entry_brackets_s'];own=str(ego.id);other=str(others[0].id)
            entered=own in entries and other in entries
            result['target_checks'].append(measured_target('both_crossing_entries_recorded',True,entered,0,'complete footprint entry brackets in same physical crossing',['participants.jsonl','authored_geometry.json','arrival_summary.json']))
            if law.endswith('250-1'):
                prior_entry=entered and entries[other][1]<entries[own][0]
                result['target_checks'].append(measured_target('other_enters_before_subject',True,prior_entry,0,'nonoverlapping original sample brackets',['arrival_summary.json','participants.jsonl']))
        if law.endswith('250-1'):
            entries=result['measured_values']['arrival']['entry_brackets_s'];exits=result['measured_values']['arrival']['exit_brackets_s'];own=str(ego.id);other=str(others[0].id)
            clearance_confirmed=own in entries and other in exits and exits[other][1]<entries[own][0]
            overlapping_entry=own in entries and other in exits and entries[own][1]<exits[other][0]
            requested=branch=='prior_entry_yield'
            measured=clearance_confirmed if requested else overlapping_entry
            result['measured_values']['precedence_evidence']={'ego_after_other_cleared':clearance_confirmed,'ego_entered_before_other_cleared':overlapping_entry,'source':'arrival_summary.json','legal_yield_standard':'unresolved; target is physical entry/clearance order only'}
            result['target_checks'].append(measured_target('requested_clearance_order_realized',True,measured,0,'nonoverlapping full-footprint entry/exit original-sample brackets; no danger cutoff',['arrival_summary.json','participants.jsonl']))
        if law.endswith('250-2'):
            summary=result['measured_values']['arrival'];entries=summary['entry_brackets_s'];own=str(ego.id);other=str(others[0].id)
            if own not in entries or other not in entries:raise CapabilityError('Cannot summarize missing actual crossing entry')
            a,b=entries[own],entries[other];difference=(a[0]+a[1]-b[0]-b[1])/2;event_time=max(a[1],b[1])
            with (out/'actual_entry_offset.jsonl').open('x') as stream:stream.write(json.dumps({'time_s':event_time,'value':difference})+'\n')
            result['realized_observables']['actual_entry_offset']={'value':difference,'unit':'s','method':'ego minus other full-footprint entry bracket midpoints; raw bracket uncertainty retained','time_window':'original entry events','statistic':'mean','sample_window_s':[event_time,event_time],'reference':'actual_entry_offset.jsonl'}
            result['measured_values']['entry_offset_bracket_s']=[a[0]-b[1],a[1]-b[0]]
            releases={}
            for sample in samples:
                for control in sample['applied_controls']:
                    if control['throttle']>0 and control['actor_id'] not in releases:releases[control['actor_id']]=sample['time_s']
            if ego.id not in releases or others[0].id not in releases:raise CapabilityError('Missing actual applied-throttle release event')
            actual_release=releases[ego.id]-releases[others[0].id];requested_release=case['variable_assignments'].get('commanded_release_offset_s',{'value':0.})['value']
            result['measured_values']['actual_applied_release_offset_s']=actual_release
            result['target_checks'].append(measured_target('applied_controller_release_offset',requested_release,actual_release,.050001,'first actual positive-throttle original-frame timestamps, not inferred vehicle arrival',['participants.jsonl','trace.jsonl']))
        if law.endswith('227-1'):
            difference=(samples[-1]['ego']['heading_deg']-samples[0]['ego']['heading_deg']+180)%360-180
            result['measured_values']['net_heading_change_deg']=difference
            result['target_checks'].append(measured_target('opposite_direction_completed',180.,abs(difference),10.,'actual original body heading difference; engineering completion criterion',['participants.jsonl','road.xodr']))
        if law.endswith('600-1a'):
            if braking_start is None:raise CapabilityError('No physical braking episode')
            braking=samples[braking_start:];distance=braking[-1]['distance_m']-braking[0]['distance_m'];(out/'stopping_summary.json').write_text(json.dumps({'distance_m':distance,'sample_window_s':[braking[0]['time_s'],braking[-1]['time_s']],'method':'actual trajectory from original brake onset through stop; not a universal stopping model'}))
            result['target_checks'].append(measured_target('physical_stop',True,samples[-1]['ego']['speed_mps']<.15,0,'actual terminal velocity after commanded braking',['participants.jsonl','stopping_summary.json']))
        if law.endswith('220-1'):
            signed=sum(sum(p['ego']['velocity_mps'][i]*p['road']['forward'][i] for i in (0,1)) for p in samples[-100:])/len(samples[-100:])
            requested=-1 if branch=='opposite_direction' else 1
            result['target_checks'].append(measured_target('actual_motion_direction',requested,1 if signed>0 else -1,0,'actual velocity dot native designated lane direction',['participants.jsonl','road.xodr']))
        if law.endswith('413-2'):
            with (out/'optical_signal.jsonl').open('x') as stream:
                for optical in optical_samples:stream.write(json.dumps(optical)+'\n')
            result['optical_signal_raw_reference']='optical_signal.jsonl'
            from signaling import continuous_signal_distance
            first=samples[0]['ego']['heading_deg'];onset=next((i for i,s in enumerate(samples) if abs((s['ego']['heading_deg']-first+180)%360-180)>5),None)
            if onset is None:raise CapabilityError('No actual right-turn course onset')
            signal_rows=[dict(time_s=s['time_s'],position=s['ego']['position_m'],right_indicator=bool(s['lamps']&int(carla.VehicleLightState.RightBlinker))) for s in samples]
            (out/'signal_summary.json').write_text(json.dumps(continuous_signal_distance(signal_rows,onset),indent=2));result['optical_signal_evidence']={'video_reference':'camera-1.webm','view':'close rear-side actual RGB','review_status':'requires original footage review; API bit not emitted-light proof'}
            result['target_checks'].append(measured_target('right_turn_course_onset',True,onset is not None,0,'actual heading relative to original approach; 5deg engineering onset',['participants.jsonl','signal_summary.json']))
        # Resource errors are result failures; success is possible only after strict
        # original-output validation. Always close encoders before ffprobe.
    except BaseException as exc:
        result['termination_reason']=type(exc).__name__+': '+str(exc);result['physical_failure_flags'].append('runtime_or_capability_failure')
    finally:
        errors=resources.close();result['cleanup_errors']=errors
        if errors:result['physical_failure_flags'].append('resource_cleanup_failure')
        for sig,handler in prior.items():signal.signal(sig,handler)
    try:validate_output(out,result,case['recording_description']);result['output_contract_confirmed']=True
    except Exception as exc:result['output_contract_confirmed']=False;result['output_contract_error']=str(exc)
    with (out/'result.json').open('x') as stream:json.dump(result,stream,indent=2)
    return 0 if result['output_contract_confirmed'] else 2

class OpticalTap:
    """Observe the exact BGRA bytes also sent to the original video encoder.

    Full-frame and rear-body ROI values are supporting raw measurements. They do
    not assert perception or that arbitrary brightness variation is lamp flashing.
    """
    def __init__(self,stream,width,height,history):self.stream=stream;self.width=width;self.height=height;self.history=history;self.context={}
    @property
    def closed(self):return self.stream.closed
    def close(self):return self.stream.close()
    def write(self,data):
        if len(data)!=self.width*self.height*4:raise ValueError('RGB byte count mismatch')
        roi=self.context.get('roi',[0,0,self.width,self.height]);x0,y0,x1,y1=roi
        values=[]
        for y in range(y0,y1,2):
            for x in range(x0,x1,2):
                index=(y*self.width+x)*4;values.append(.0722*data[index]+.7152*data[index+1]+.2126*data[index+2])
        if not values:raise CapabilityError('Rear-body optical ROI outside original camera')
        self.history.append(dict(self.context,mean_luminance=sum(values)/len(values),min_luminance=min(values),max_luminance=max(values),roi=roi,method='original BGRA rear-body crop; supporting evidence only, not lamp classifier'))
        return self.stream.write(data)

def rear_body_roi(camera,ego,width,height):
    matrix=camera.get_transform().get_inverse_matrix();fov=float(camera.attributes.get('fov','90'));focal=width/(2*math.tan(math.radians(fov)/2));pixels=[]
    for vertex in ego.bounding_box.get_world_vertices(ego.get_transform()):
        world=[vertex.x,vertex.y,vertex.z,1];local=[sum(a*b for a,b in zip(row,world)) for row in matrix]
        if local[0]<=.01:continue
        pixels.append([width/2+local[1]*focal/local[0],height/2-local[2]*focal/local[0]])
    if not pixels:raise CapabilityError('Subject body behind original lamp-view camera')
    x0=max(0,int(min(p[0] for p in pixels)));x1=min(width,int(max(p[0] for p in pixels))+1);y0=max(0,int(min(p[1] for p in pixels)));y1=min(height,int(max(p[1] for p in pixels))+1)
    if x1<=x0 or y1<=y0:raise CapabilityError('Subject body outside original lamp view')
    return [x0,y0,x1,y1]
