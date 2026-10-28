#!/usr/bin/env python3
"""Law-scoped physical preparation: observed telemetry, no legal verdict."""
import argparse,copy,json,math,pathlib,signal,sys,xml.etree.ElementTree as ET
from contracts import validate_output,measured_target,route_contained,summarize
from recording import Recording,Resources
ROOT=pathlib.Path(__file__).resolve().parent
DT=.05

def speed(v):return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def wrap(a):return (a+math.pi)%(2*math.pi)-math.pi

def route(c,case):
    
    if c.get('native_inventory'):return c['native_inventory']['route']
    mechanism=c['mechanism'];v=case['variable_assignments'];approach=v.get('commanded_approach_lateral',{}).get('value',1.75);exitx=v.get('commanded_exit_lateral',{}).get('value',1.75)
    path=[[-90+i,approach] for i in range(79)]
    if mechanism=='yield':path=[[-4,approach]]
    if mechanism in ('turn','yield'):
        for i in range(1,41):
            u=i/40.;path.append([(1-u)**2*(-4 if mechanism=='yield' else -12)+2*(1-u)*u*exitx+u*u*exitx,(1-u)**2*approach+2*(1-u)*u*approach+u*u*(-12)])
        path += [[exitx,-12-i] for i in range(1,49)]
    elif mechanism=='lane_change':
        path += [[-12+i,approach+3.5*(.5-.5*math.cos(min(i/40.,1)*math.pi))] for i in range(1,83)]
    else:path += [[-12+i,approach] for i in range(1,103)]
    return path

def command(position,yaw,velocity,path,target):
    closest=min(range(len(path)),key=lambda i:math.hypot(path[i][0]-position[0],path[i][1]-position[1]))
    lookahead=4.+velocity*.4;goal=path[-1]
    for point in path[closest:]:
        if math.dist(position,point)>=lookahead:goal=point;break
    alpha=wrap(math.atan2(goal[1]-position[1],goal[0]-position[0])-math.radians(yaw))
    # Bicycle-model steering request; native observed yaw/velocity provide feedback.
    steer=math.atan2(2*2.8*math.sin(alpha),max(1,lookahead))/.65;effort=.65*(target-velocity)
    return dict(throttle=max(0,min(.65,effort)),brake=max(0,min(1,-effort)),steer=max(-.8,min(.8,steer)))

def build_road(c):
    tree=ET.parse(ROOT/'road-template.xodr');root=tree.getroot();root.find('header').set('name',c['assignment_id'])
    for road in root.findall('road'):
        if c.get('one_way'):
            for section in road.findall('./lanes/laneSection'):
                left=section.find('left')
                if left is not None:section.remove(left)
                for mark in section.findall('./center/lane/roadMark'):mark.set('color','white')
        # Do not mistake OpenDRIVE signal metadata for rendered native devices.
        for tag in ('objects','signals'):
            node=road.find(tag)
            if node is not None:road.remove(node)
    return ET.tostring(root,encoding='unicode')

def polygons(config=None):
 if config and config.get('native_inventory'):return config['native_inventory']['driving_polygons']
 if json.loads((ROOT/'config.json').read_text()).get('one_way'):return [[[-400,0],[400,0],[400,7],[-400,7]],[[0,-400],[7,-400],[7,400],[0,400]]]
 return [[[-400,-7],[400,-7],[400,7],[-400,7]],[[-7,-400],[7,-400],[7,400],[-7,400]]]
def footprint_inside(vertices,config=None):
    for v in vertices:
        if not any(_contained(v[:2],p) for p in polygons(config)):return False
    return True

def _contained(v,p):
    try:route_contained([v],p);return True
    except ValueError:return False

def atom_measurements(required,state,participants,geometry,history,event=None):
    """Raw value-free evidence only: authored region and native motion stay distinct."""
    ego=state;wp=ego['native_lane'];body=ego['body_vertices_m'];p=ego['position_m'];now=ego['time_s'];previous=history[-1] if history else ego
    motion={'position_m':p,'heading_deg':ego['heading_deg'],'speed_mps':ego['speed_mps'],'body_vertices_m':body,'previous_position_m':previous['position_m'],'time_s':now,'previous_time_s':previous['time_s']}
    others=[x for x in participants if x['actor_id']!=ego['actor_id']]
    relation={'ego':motion,'others':others,'method':'native actor position, velocity, bounding box and synchronized original frame; no qualitative predicate or mental state inferred'}
    static={'authored_geometry':geometry,'native_lane':wp,'method':'native map waypoint plus authored road polygons; legal boundaries remain explicit synthetic assumptions'}
    values={}
    for atom in required:
        if atom=='oncoming_x':value=others[0]['position_m'][0]
        elif atom=='caravan_gap':value=min(v[0] for v in others[0]['body_vertices_m'])-max(v[0] for v in ego['body_vertices_m'])
        elif atom=='st.sight_distance':
            visibility=event.get('visibility') if event else None
            if not visibility or visibility.get('unknown_reason'):raise ValueError('Original sight-distance capability unavailable')
            approaches=visibility.get('approaches',[])
            if not approaches or set(visibility.get('required_lane_ids',[]))!={a['lane_id'] for a in approaches} or any(a.get('unknown_reason') or not a.get('any_body_sight_horizon') or a['any_body_sight_horizon'].get('unknown') or a['any_body_sight_horizon'].get('bound')=='route_limit' for a in approaches):raise ValueError('Incomplete original nine-point incoming visibility coverage')
            value=visibility
        elif atom=='rel.visible':
            if not event or 'relations' not in event.get('original_observations',{}):raise ValueError('Original visibility relations unavailable')
            value={'relations':event['original_observations']['relations'],'method':'original-frame actual eye-to-body ray evidence; no perception assertion'}
        elif atom=='dev.stop_sign':
            if not geometry.get('native_stop_sign'):raise ValueError('Native rendered governed stop-sign evidence unavailable')
            value=geometry['native_stop_sign']
        elif atom=='dev.governs':
            value={'native_topology':geometry.get('native_lane_topology',[]),'native_stop_sign':geometry.get('native_stop_sign'),'authored_geometry':geometry,'method':'native topology and source-bound governed lane, no proximity-only inference'}
        elif atom=='kin.speed':value=ego['speed_mps']
        elif atom=='kin.position':value={'world_m':p,'body_vertices_m':body}
        elif atom=='sig.turn_indicator':value={'ego_lamp_bits':ego['lamp_bits'],'participants':[{k:x[k] for k in ('actor_id','lamp_bits')} for x in others],'method':'native get_light_state; emitted-light evidence separately required'}
        elif atom.startswith('st.') or atom in ('dev.stop_sign','dev.governs'):value=static
        elif atom=='ru.trailer_or_combination':value={'actors':[{'actor_id':x['actor_id'],'blueprint':x['blueprint'],'body_vertices_m':x['body_vertices_m']} for x in participants],'authored_towing':False,'method':'spawned registry and original actor blueprint inventory; no omitted combinations'}
        elif atom=='rel.surface_gap':
            ordered=sorted(participants,key=lambda x:x['position_m'][0]);gaps=[]
            for a,b in zip(ordered,ordered[1:]):gaps.append({'rear_actor':a['actor_id'],'front_actor':b['actor_id'],'longitudinal_bumper_gap_m':min(v[0] for v in b['body_vertices_m'])-max(v[0] for v in a['body_vertices_m'])})
            value={'gaps':gaps,'participants':participants,'method':'world x projected bounding-box surfaces; no danger or sufficient-space judgment'}
        elif atom.startswith('drv.') or atom.startswith('rel.'):value=relation
        else:raise ValueError('No measurement implementation for atom '+atom)
        values[atom]=value
    return values

def state(actor,time_s,mapping):
    t=actor.get_transform();wp=mapping.get_waypoint(t.location);v=actor.get_velocity()
    return dict(actor_id=actor.id,blueprint=actor.type_id,time_s=time_s,position_m=[t.location.x,t.location.y,t.location.z],heading_deg=t.rotation.yaw,speed_mps=speed(v),velocity_mps=[v.x,v.y,v.z],lamp_bits=int(actor.get_light_state()),body_vertices_m=[[p.x,p.y,p.z] for p in actor.bounding_box.get_world_vertices(t)],native_lane=None if wp is None else dict(road_id=wp.road_id,lane_id=wp.lane_id,s_m=wp.s,is_junction=wp.is_junction,lane_width_m=wp.lane_width))

def check():
    c=json.loads((ROOT/'config.json').read_text());p=json.loads((ROOT/'proposals/cases.json').read_text());assert set(c['supported_case_ids'])=={x['case_id'] for x in p['cases']}
    assert len(ET.fromstring(build_road(c)).findall('road'))==6
    for case in p['cases']:
        path=route(c,case);assert len(path)>10 and all(math.dist(a,b)<4 for a,b in zip(path,path[1:]));assert all(any(_contained(x,p) for p in polygons()) for x in path)
        assert all(x.get('value') is None for x in case['variable_assignments'].values() if x['kind']=='subject_behavior')
    assert len(c['cameras'])==4 and c['max_ticks']>0
    print('Offline road/route/cases/recording checks passed; no live physical evidence asserted')

def run(args):
    import carla
    c=json.loads((ROOT/'config.json').read_text());case=next(x for x in json.loads((ROOT/'proposals/cases.json').read_text())['cases'] if x['case_id']==(args.case_id or c['default_case_id']))
    if args.sweep_value is not None:
        grid=c.get('judgment_sweep_grid',[])
        if args.sweep_value not in grid:raise ValueError('Value outside frozen physical grid')
        case=copy.deepcopy(case);case['case_id']=c['assignment_id']+'__judgment_x_'+str(int(args.sweep_value));case['target_type']='judgment_sweep';case['variable_assignments']['commanded_oncoming_x']={'kind':'world_setup','value':args.sweep_value,'unit':'m'};case['variable_assignments']['commanded_yield']['value']=False
    if case['target_type']=='baseline':raise ValueError('Baseline is definition-only and unselected')
    if args.inventory:
        c['native_inventory']=json.loads(pathlib.Path(args.inventory).read_text())
    if any(x['category']=='external_asset' for x in c.get('external_barriers',[])) and not c.get('native_inventory'):
        raise RuntimeError('Native stop-sign/crosswalk inventory binding required: --inventory PATH')
    out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():raise FileExistsError('Retain previous attempt; select a new output directory')
    resources=Resources();actors=[];recording=None;history=[];participant_history=[];footprints=[];frames=[];samples=[];collisions=[];stop=[False];cleanup=[]
    result=dict(setup_confirmed=False,behavior_attempted=False,maneuver_completed=False,termination_reason='setup_failure',physical_failure_flags=[],measured_values={},target_checks=[],recording_description=c['recording_description'],recording_evidence=[],realized_observables={},trace_reference='trace.jsonl',video_references=[],video_frame_map_reference='video_frame_map.jsonl',requested_variable_assignments=case['variable_assignments'])
    try:
        for sig in (signal.SIGINT,signal.SIGTERM):
            previous=signal.signal(sig,lambda *_:stop.__setitem__(0,True));resources.own(lambda s=sig,p=previous:signal.signal(s,p))
        client=carla.Client(args.host,args.port);client.set_timeout(30)
        if client.get_client_version()!=client.get_server_version():raise RuntimeError('Client/server version mismatch')
        world=client.load_world(c['native_inventory']['world']) if c.get('native_inventory') else client.generate_opendrive_world(build_road(c));old=world.get_settings();resources.own(lambda:world.apply_settings(old));settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=DT;world.apply_settings(settings);mapping=world.get_map();lib=world.get_blueprint_library()
        runtime=ROOT.parents[1]/'runtime/python'
        if runtime.is_dir():sys.path.insert(0,str(runtime))
        path=route(c,case);halt_released=False;halt_settled=0;vars=case['variable_assignments'];speed_target=vars['commanded_approach_speed']['value'];mechanism=c['mechanism']
        def spawn(x,y,yaw=0):
            actor=world.spawn_actor(lib.find('vehicle.tesla.model3'),carla.Transform(carla.Location(x=x,y=y,z=.6),carla.Rotation(yaw=yaw)));actors.append(actor);resources.own(actor.destroy);return actor
        initial_yaw=math.degrees(math.atan2(path[1][1]-path[0][1],path[1][0]-path[0][0]));ego=spawn(*path[0],yaw=initial_yaw);participants=[ego];other_routes={}
        if mechanism=='yield':
            oncoming_x=vars.get('commanded_oncoming_x',{}).get('value',6);other=spawn(oncoming_x,-1.75,180);participants.append(other);other_routes[other.id]=[[oncoming_x-i,-1.75] for i in range(150)]
        if mechanism=='caravan':
            gap=vars['commanded_gap']['value'];lead=spawn(path[0][0]+gap+4.8,1.75);participants.append(lead);other_routes[lead.id]=[[lead.get_location().x+i,1.75] for i in range(501)]
            merger=spawn(path[0][0]+gap*.5,5.25);participants.append(merger);other_routes[merger.id]=[[merger.get_location().x+i,5.25-3.5*(.5-.5*math.cos(min(i/50.,1)*math.pi))] for i in range(501)]
        collision=world.spawn_actor(lib.find('sensor.other.collision'),carla.Transform(),attach_to=ego);resources.own(collision.destroy);resources.own(collision.stop);collision.listen(lambda event:collisions.append(dict(frame=event.frame,other_actor=event.other_actor.id,normal_impulse=[event.normal_impulse.x,event.normal_impulse.y,event.normal_impulse.z])))
        geometry=dict(driving_polygons=polygons(c),intersection_polygon=[[-7,-7],[7,-7],[7,7],[-7,7]],centre_lines=[dict(points=[[-400,0],[400,0]],opposite_direction_lanes=not c.get('one_way',False)),dict(points=[[0,-400],[0,400]],opposite_direction_lanes=not c.get('one_way',False))],lane_edges_y_m=[-7,-3.5,0,3.5,7],source='authored OpenDRIVE physical driving surfaces and markings; legal public-way/region status explicit assumptions',assumptions=vars['authored_context']['value'])
        geometry['native_lane_topology']=[dict(source=dict(road_id=a.road_id,lane_id=a.lane_id,s_m=a.s),destination=dict(road_id=b.road_id,lane_id=b.lane_id,s_m=b.s)) for a,b in mapping.get_topology()]
        if c.get('native_inventory'):
            inv=c['native_inventory'];sign=world.get_actor(inv['stop_sign_actor_id'])
            if sign is None or not sign.type_id.startswith('traffic.stop'):raise RuntimeError('Required native stop-sign actor not found')
            geometry['native_stop_sign']=dict(actor_id=sign.id,type_id=sign.type_id,transform=str(sign.get_transform()),governed_lane=inv['governed_lane'],governance_source=inv['governance_evidence'],crosswalk_polygon=inv['crosswalk_polygon'],sidewalk_source=inv['sidewalk_evidence'])
        (out/'contexts.json').write_text(json.dumps({'authored_context':vars['authored_context']['value']}));(out/'config.json').write_text(json.dumps(c));(out/'geometry.json').write_text(json.dumps(geometry));(out/'versions.json').write_text(json.dumps(dict(client=client.get_client_version(),server=client.get_server_version(),map=mapping.name)))
        recording=Recording(client,ego,out,case['case_id'],c['recording_description'],c['cameras'],c['required_atoms']);resources.own(recording.close)
        result['setup_confirmed']=True;result['behavior_attempted']=True;start_time=None
        for tick in range(c['max_ticks']):
            if stop[0]:result['termination_reason']='signal';break
            loc=ego.get_location();tf=ego.get_transform();v=speed(ego.get_velocity());target=speed_target
            if mechanism=='yield' and vars['commanded_yield']['value'] and loc.y>-1:
                other_state=state(participants[1],0,mapping)
                if max(p[0] for p in other_state['body_vertices_m'])>-7:target=0
            if mechanism=='stop' and vars['commanded_halt']['value'] and not halt_released:
                center=c['native_inventory']['stop_center_x'];target=min(target,math.sqrt(2*1.5*max(0,center-loc.x)))
                if abs(loc.x-center)<.5 and v<.03:halt_settled+=1
                if halt_settled>=4:halt_released=True
            if mechanism=='caravan':
                lead_state=state(participants[1],0,mapping);ego_state=state(ego,0,mapping);gap=min(p[0] for p in lead_state['body_vertices_m'])-max(p[0] for p in ego_state['body_vertices_m']);target=max(0,min(speed_target+2,speed_target+.3*(gap-vars['commanded_gap']['value'])))
            ego.apply_control(carla.VehicleControl(**command((loc.x,loc.y),tf.rotation.yaw,v,path,target)))
            lamp=vars.get('commanded_signal',{}).get('value',False)
            ego.set_light_state(carla.VehicleLightState.RightBlinker if lamp else carla.VehicleLightState.NONE)
            for other in participants[1:]:
                t=other.get_transform();other.apply_control(carla.VehicleControl(**command((t.location.x,t.location.y),t.rotation.yaw,speed(other.get_velocity()),other_routes[other.id],1. if mechanism=='yield' else speed_target)))
            frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds;start_time=now if start_time is None else start_time
            measured=[state(a,now,mapping) for a in participants];es=measured[0]
            def observations(row,event):return atom_measurements([x['name'] for x in c['recording_description']['channels']],es,measured,geometry,history,event)
            recording.tick(frame,now,observations,extra={'ego_lamp_bits':es['lamp_bits']});history.append(es);participant_history.append(dict(time_s=now,participants=measured));footprints.append(dict(time_s=now,vertices=es['body_vertices_m']));frames.append(frame);samples.append(dict(time_s=now,value=es['speed_mps']))
            if collisions:result['termination_reason']='collision';break
            if not footprint_inside(es['body_vertices_m'],c):result['termination_reason']='footprint_departure';break
            if math.dist(es['position_m'][:2],path[-1])<2:result['maneuver_completed']=True;result['termination_reason']='route_end';break
        else:result['termination_reason']='timeout'
        def save_lines(name,rows):(out/name).write_text(''.join(json.dumps(x)+'\n' for x in rows))
        save_lines('participants.jsonl',participant_history);save_lines('footprints.jsonl',footprints);save_lines('collisions.jsonl',collisions)
        result.update(recording.result_fields());result['recording_evidence'].append(dict(name='authored_context',unit='object',reference='contexts.json'));result['required_participant_ids']=[a.id for a in participants];result['participant_history_reference']='participants.jsonl';result['footprint_reference']='footprints.jsonl';result['driving_polygons']=polygons(c)
        checks=[measured_target('collision_free',True,not collisions,0,'original collision sensor','collisions.jsonl'),measured_target('route_footprint_containment',True,all(footprint_inside(s['vertices'],c) for s in footprints),0,'all world-space body vertices in authored driving-surface union','footprints.jsonl')]
        if c['law_id'].endswith('400-2a'):
            approach=[s for s in history if -55<s['position_m'][0]<-15];measured=sum(s['position_m'][1] for s in approach)/len(approach) if approach else None;checks.append(measured_target('commanded_approach_lateral',vars['commanded_approach_lateral']['value'],measured,.6,'mean native body-centre y on authored straight approach x in (-55,-15); full footprint retained','footprints.jsonl'))
        elif c['law_id'].endswith('400-2b'):
            exits=[s for s in history if s['position_m'][1]<-15];measured=sum(s['position_m'][0] for s in exits)/len(exits) if exits else None;checks.append(measured_target('commanded_exit_lateral',vars['commanded_exit_lateral']['value'],measured,.6,'mean native body-centre x on destination y<-15; full footprint retained','footprints.jsonl'))
        elif mechanism=='yield' and case['target_type']=='judgment_sweep':
            checks.append(measured_target('commanded_oncoming_x',vars['commanded_oncoming_x']['value'],participant_history[0]['participants'][1]['position_m'][0],.2,'first original oncoming body centre x; no hazard interpretation','participants.jsonl'))
            result['realized_observables']['oncoming_x']=dict(value=participant_history[0]['participants'][1]['position_m'][0],unit='m',method='first original oncoming body-centre world x on fixed opposite-direction route',time_window='first original recorded tick only',statistic='max',sample_window_s=[history[0]['time_s'],history[0]['time_s']],reference='channels/oncoming_x.jsonl')
        elif mechanism=='yield':
            event=next((i for i,s in enumerate(history) if s['position_m'][1]<-1),None);other_clear=event is not None and max(p[0] for p in participant_history[event]['participants'][1]['body_vertices_m'])<-7;checks.append(measured_target('yield_before_conflict_entry',vars['commanded_yield']['value'],bool(other_clear),0,'original simultaneous body polygons at first ego centre y<-1; no hazard threshold','participants.jsonl'))
        elif mechanism=='caravan':
            gaps=[min(p[0] for p in h['participants'][1]['body_vertices_m'])-max(p[0] for p in h['participants'][0]['body_vertices_m']) for h in participant_history[-100:]];measured=sum(gaps)/len(gaps) if gaps else None
            if gaps:result['realized_observables']['caravan_gap']=dict(value=measured,unit='m',method='world-x bumper-surface gap between ego and lead from original body vertices',time_window='final 100 original samples before route completion',statistic='mean',sample_window_s=[participant_history[-min(100,len(participant_history))]['time_s'],participant_history[-1]['time_s']],reference='channels/caravan_gap.jsonl')
            checks.append(measured_target('commanded_gap',vars['commanded_gap']['value'],measured,2.,'mean original bounding-box bumper gap in final 100 ticks; engineering tolerance only','participants.jsonl'))
        elif mechanism=='stop':
            boundary=c['native_inventory']['crosswalk_boundary_x'];halt=any(s['speed_mps']<.03 and max(p[0] for p in s['body_vertices_m'])<boundary for s in history);checks.append(measured_target('commanded_halt',vars['commanded_halt']['value'],halt,0,'native low-speed cessation bracket before inventory-bound near-side crosswalk; engineering resolution is not a legal minimum span','footprints.jsonl'))
        elif mechanism=='lane_change':
            checks.append(measured_target('commanded_signal',vars['commanded_signal']['value'],bool(history and all(s['lamp_bits']&int(carla.VehicleLightState.RightBlinker) for s in history)),0,'native lamp bits, emitted light separately externally calibrated','participants.jsonl'))
        result['target_checks']=checks;result['measured_values']={'captured_frames':len(history),'final_position_m':history[-1]['position_m'] if history else None}
        if mechanism=='lane_change' and c.get('external_barriers'):result['physical_failure_flags'].append('emitted_indicator_light_requires_original_RGB_calibration_and_review')
        if not result['maneuver_completed']:result['physical_failure_flags'].append('maneuver_incomplete')
        if not all(x['matched'] for x in checks):result['physical_failure_flags'].append('target_mismatch')
    except BaseException as exc:
        result['physical_failure_flags'].append(type(exc).__name__+': '+str(exc));result['termination_reason']='runtime_failure'
    finally:
        cleanup=resources.close()
        if recording is not None:
            result.update(recording.result_fields());result['recording_evidence'].append(dict(name='authored_context',unit='object',reference='contexts.json'));cleanup+=recording.close_errors
        result['cleanup_errors']=cleanup
        if cleanup:result['physical_failure_flags'].append('cleanup_failure')
        (out/'cleanup.json').write_text(json.dumps(dict(errors=cleanup,owned_actors_destroyed=not cleanup,world_settings_restored=not cleanup)))
        result['cleanup_reference']='cleanup.json'
        try:validate_output(out,result,c['recording_description']);valid=True
        except (ValueError,KeyError,TypeError,OSError) as exc:valid=False;result['physical_failure_flags'].append('output_validation: '+str(exc))
        (out/'result.json').write_text(json.dumps(result,indent=2))
    return 0 if valid else 2

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--output-dir');ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=2000);ap.add_argument('--case-id');ap.add_argument('--sweep-value',type=float);ap.add_argument('--inventory');args=ap.parse_args()
    if args.check:check()
    elif not args.output_dir:ap.error('--output-dir is required')
    else:sys.exit(run(args))
