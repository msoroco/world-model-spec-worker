"""Draft physical runner. --check performs no runtime imports or network access."""
import argparse,ast,json,math,pathlib,sys,signal,queue,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parent

def load(): return json.loads((ROOT/'config.json').read_text())
def speed(v): return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def wrap(a): return (a+math.pi)%(2*math.pi)-math.pi

def command(position,yaw,velocity,path,index,target,reverse=False):
    """Monotone pure-pursuit route and bounded P speed servo; no teleportation."""
    while index<len(path)-1 and math.hypot(position[0]-path[index][0],position[1]-path[index][1])<3: index+=1
    j=index
    while j<len(path)-1 and math.hypot(position[0]-path[j][0],position[1]-path[j][1])<max(4.,velocity*.7): j+=1
    dx,dy=path[j][0]-position[0],path[j][1]-position[1]
    heading=yaw+(math.pi if reverse else 0)
    alpha=wrap(math.atan2(dy,dx)-heading)
    steering=math.atan2(2*2.8*math.sin(alpha),max(1.,math.hypot(dx,dy)))/.65
    steering=max(-1.,min(1.,steering))*(-1 if reverse else 1)
    error=target-velocity
    return dict(throttle=max(0.,min(.7,.3*error)),brake=max(0.,min(1.,-.5*error)),steer=steering,reverse=reverse),index

def surface_gap(ego,lead):
    """Signed along-heading separation using measured world body corners."""
    t=ego.get_transform(); h=math.radians(t.rotation.yaw); axis=(math.cos(h),math.sin(h))
    def extent(actor):
        return [p.x*axis[0]+p.y*axis[1] for p in actor.bounding_box.get_world_vertices(actor.get_transform())]
    return min(extent(lead))-max(extent(ego))

def static_check():
    c=load();plan=json.loads((ROOT/'case-plan.json').read_text());x=ET.parse(ROOT/'road.xodr').getroot()
    assert x.tag=='OpenDRIVE' and x.findall('road')
    assert c['actor']==plan['actor'] and c['law_id']==plan['law_id']
    assert set(c['supported_case_ids'])=={i['case_id'] for i in plan['cases']}
    assert len(c['cameras'])==4 and c['hz']==20
    assert all(r['length']>=250 for r in c['route_extents'])
    for f in ('runner.py','finalize.py','geometry.py'):ast.parse((ROOT/f).read_text())
    from geometry import validate_map
    validate_map(ROOT/'road.xodr',c['mechanism'])
    if c['mechanism']=='uturn':
        from geometry import validate_uturn_footprint
        for case in c['cases']:validate_uturn_footprint(case['variable_assignments']['maneuver_station_m']['value'])
    construction=json.loads((ROOT/'construction.json').read_text())
    for f in construction['files']:assert (ROOT/f['path']).read_text()==f['content'],f['path']
    assert {o['name'] for o in plan['observations']} <= {i['name'] for i in construction['recording_description']['channels']}
    for proposal in (ROOT/'constructions').glob('*.json'):
        d=json.loads(proposal.read_text()); cfg=next(f for f in d['files'] if f['path']=='config.json')
        assert json.loads(cfg['content'])['selected_case_id']==d['case_id']
        assert next(f for f in d['files'] if f['path']=='runner.py')['content']==(ROOT/'runner.py').read_text()
    print(json.dumps({'offline':True,'case_count':len(plan['cases']),'status':'partial','gaps':c['delivery_gaps']}))

def route(world,c,case):
    m=world.get_map();kind=c['mechanism'];a=case['variable_assignments'];start=a['route_start_s']['value']
    def point(road,s,lane=-1):
        w=m.get_waypoint_xodr(road,lane,s)
        if w is None:raise RuntimeError('Native route missing road/lane/station '+str((road,lane,s)))
        p=w.transform.location; return [p.x,p.y,p.z+.35]
    if kind=='yield': return [point(1,s) for s in range(int(start),490,2)]+[point(11,s) for s in range(0,20,2)]+[point(2,s) for s in range(0,100,2)]
    if kind=='reverse':
        # Fixed straight reverse route crosses native junction connectors when selected.
        return [point(1,s) if s<490 else point(11,s-490) if s<=510 else point(2,s-510) for s in range(int(start),int(start)-60,-2)]
    if kind=='uturn':
        station=a['maneuver_station_m']['value'];p=point(1,station);result=[point(1,s) for s in range(int(start),int(station),2)]
        result += [[p[0]+6*math.sin(t),p[1]-6+6*math.cos(t),p[2]] for t in [i*math.pi/40 for i in range(41)]]
        result += [[p[0]-i,p[1]-12,p[2]] for i in range(2,60,2)];return result
    return [point(1,s) for s in range(int(start),int(start)+200,2)]

def cleanup_resources(capture,streams,sensors,actors,world,old,handlers,result,out,frame_map=None):
    """Attempt every cleanup even if recorder/capture finalization fails."""
    errors=[]
    def attempt(label,action):
        try:action()
        except BaseException as exc:errors.append({'resource':label,'error':type(exc).__name__+': '+str(exc)})
    if capture:attempt('capture',lambda:capture.close(confirmed=bool(result['maneuver_completed'])))
    if frame_map:attempt('frame_map',frame_map.close)
    for name,stream in streams.items():attempt('channel:'+name,stream.close)
    for sensor in sensors:attempt('sensor.stop',sensor.stop)
    for actor in reversed(actors):attempt('actor.destroy',actor.destroy)
    attempt('world.settings',lambda:world.apply_settings(old))
    for sig,handler in handlers.items():attempt('signal.restore',lambda sig=sig,handler=handler:signal.signal(sig,handler))
    result['cleanup_errors']=errors
    if errors:result['physical_failure_flags'].append('cleanup_failure')
    (out/'result.json').write_text(json.dumps(result,indent=2))
    return errors

def yield_reference_target(x,velocity,half_length,requested_hold,observed_hold,dt,nominal):
    # Engineering front-bumper stop margin from native junction approach endpoint.
    if observed_hold>=requested_hold:return nominal,observed_hold
    if x>475 and velocity<.05:observed_hold=min(requested_hold,observed_hold+dt)
    remaining=max(0.,490.-half_length-.5-x)
    return min(nominal,.8*remaining),observed_hold

def execute(args):
    from contracts import validate_output,measured_target,summarize
    from recording import Recording,Resources
    from measurements import project,setup
    import shutil
    c=load();case=next(i for i in c['cases'] if i['case_id']==(args.case_id or c['selected_case_id']))
    if case['target_type']=='baseline' and not args.include_baselines:raise ValueError('Baseline is not selected by default; --include-baselines required')
    out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    with (out/'attempt.json').open('x') as f:json.dump({'case_id':case['case_id']},f)
    result={'case_id':case['case_id'],'status':'draft','requested_variable_assignments':case['variable_assignments'],'measured_values':{},'target_checks':[],'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'initialization','physical_failure_flags':[],'trace_reference':'trace.jsonl','video_references':[],'video_frame_map_reference':'video_frame_map.jsonl','recording_description':case['recording_description'],'recording_evidence':[],'realized_observables':{},'external_requirements':[]}
    resources=Resources();recording=None;world=None;old=None;actors=[];handlers={};stopping={'requested':False};history=[];values=[];measurements=[];success=False
    def terminate(sig,frame):stopping['requested']=True
    try:
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):raise RuntimeError('external_asset: ffmpeg/ffprobe with VP9 encoder required')
        import carla
        # Local execution uses supplied runtime; materialized execution consumes declared PYTHONPATH.
        runtime=ROOT.parents[1]/'runtime/python'
        if runtime.is_dir():sys.path.insert(0,str(runtime))
        client=carla.Client(args.host,args.port);client.set_timeout(30.)
        if client.get_client_version()!=client.get_server_version():raise RuntimeError('external_asset: CARLA client/server version mismatch')
        world=client.generate_opendrive_world((ROOT/'road.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=1.,max_road_length=50.,wall_height=0.,additional_width=.2,smooth_junctions=True,enable_mesh_visibility=True));old=world.get_settings();resources.own(lambda:world.apply_settings(old))
        for sig in (signal.SIGINT,signal.SIGTERM):
            previous_handler=signal.signal(sig,terminate);resources.own(lambda sig=sig,handler=previous_handler:signal.signal(sig,handler))
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/c['hz'];settings.no_rendering_mode=False;world.apply_settings(settings)
        a=case['variable_assignments'];path=route(world,c,case);reverse=c['mechanism']=='reverse';bp=world.get_blueprint_library().find(c['vehicle_blueprint']);bp.set_attribute('role_name','subject')
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(*path[0]),carla.Rotation(yaw=0.)));actors.append(ego);resources.own(ego.destroy)
        if c['mechanism']=='uturn':
            from geometry import validate_uturn_footprint
            validate_uturn_footprint(a['maneuver_station_m']['value'],ego.bounding_box.extent.x,ego.bounding_box.extent.y)
        lead=None;lead_path=[];lead_index=0
        if c['mechanism']=='following':
            if 2*ego.bounding_box.extent.y<2.032:raise RuntimeError('external_asset: selected goods truck blueprint width does not meet 80-inch class')
            lead=world.spawn_actor(bp,carla.Transform(carla.Location(path[0][0]+a['commanded_surface_gap']['value']+2*ego.bounding_box.extent.x,path[0][1],path[0][2]),carla.Rotation()));actors.append(lead);resources.own(lead.destroy)
            if 2*lead.bounding_box.extent.y<2.032:raise RuntimeError('external_asset: selected lead truck blueprint width does not meet 80-inch class')
            for s in range(400,1200,2):
                w=world.get_map().get_waypoint_xodr(1,-1,float(s));p=w.transform.location;lead_path.append([p.x,p.y,p.z+.35])
            lead_index=min(range(len(lead_path)),key=lambda i:math.hypot(lead_path[i][0]-lead.get_location().x,lead_path[i][1]-lead.get_location().y))
        elif c['mechanism']=='yield':
            for road,stations in ((21,range(2,20,2)),(4,range(0,200,2))):
                for station in stations:
                    w=world.get_map().get_waypoint_xodr(road,-1,float(station))
                    if w is None:raise RuntimeError('live_measurement: native cross-participant route missing')
                    p=w.transform.location;lead_path.append([p.x,p.y,p.z+.35])
            w=world.get_map().get_waypoint_xodr(21,-1,2.);t=w.transform;t.location.z+=.35;lead=world.spawn_actor(world.get_blueprint_library().find('vehicle.lincoln.mkz_2020'),t);actors.append(lead);resources.own(lead.destroy)
        # Let the native geometry/sensors settle only through recorded frames, without hidden driving.
        receipt=setup(world,c,a);(out/'setup.json').write_text(json.dumps(receipt,indent=2));result['setup_confirmed']=True
        (out/'config.json').write_text(json.dumps(c,indent=2));(out/'context.json').write_text(json.dumps({'authored_test_context':a},indent=2))
        recording=Recording(client,ego,out,case['case_id'],case['recording_description'],c['cameras'],required_atoms=[o['name'] for o in c['observations']]);resources.own(recording.close)
        histories=(out/'participants.jsonl').open('x');resources.own(histories.close);footprints=(out/'footprints.jsonl').open('x');resources.own(footprints.close)
        result.update(required_participant_ids=[p.id for p in actors],participant_history_reference='participants.jsonl',footprint_reference='footprints.jsonl',driving_polygons=c['driving_polygons'])
        collisions=[]
        sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=ego);resources.own(sensor.destroy);resources.own(sensor.stop);sensor.listen(lambda event:collisions.append({'frame':event.frame,'other_actor_id':event.other_actor.id,'impulse':[event.normal_impulse.x,event.normal_impulse.y,event.normal_impulse.z]}))
        i=0;previous={};stationary_hold=0.;entered_gate=False
        auxiliary={}
        names=['sight_distance.minimum_from_either_approach'] if c['mechanism']=='uturn' else ['subject_truck_width','lead_truck_width'] if c['mechanism']=='following' else ['backing_intersection_overlap','backing_crosswalk_overlap'] if c['mechanism']=='reverse' else []
        for name in names:
            stream=(out/(name+'.jsonl')).open('x');resources.own(stream.close);auxiliary[name]={'stream':stream,'samples':[]}
        def save_scalar(name,time_s,value):
            row={'time_s':time_s,'value':value};auxiliary[name]['samples'].append(row);auxiliary[name]['stream'].write(json.dumps(row)+'\n')
        for tick in range(int(c['duration_s']*c['hz'])):
            if stopping['requested']:result['termination_reason']='signal';break
            t=ego.get_transform();v=speed(ego.get_velocity());target=a['commanded_approach_speed']['value']
            if c['mechanism']=='yield' and t.location.x>475:
                entered_gate=True
                target,stationary_hold=yield_reference_target(t.location.x,v,ego.bounding_box.extent.x,a['yield_hold_s']['value'],stationary_hold,1/c['hz'],target)
            if c['mechanism']=='following':target=max(0.,min(12.,target+.15*(surface_gap(ego,lead)-a['commanded_surface_gap']['value'])))
            ctl,i=command((t.location.x,t.location.y),math.radians(t.rotation.yaw),v,path,i,target,reverse);ego.apply_control(carla.VehicleControl(**ctl));result['behavior_attempted']=True
            if lead:
                lt=lead.get_transform();lead_target=a['commanded_approach_speed']['value'] if c['mechanism']=='following' else (3. if entered_gate else 0.)
                if lead_index==len(lead_path)-1:lead_target=0.
                control,lead_index=command((lt.location.x,lt.location.y),math.radians(lt.rotation.yaw),speed(lead.get_velocity()),lead_path,lead_index,lead_target);lead.apply_control(carla.VehicleControl(**control))
            frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds
            captured={}
            def measure(row,event):
                observation,participants,body=project(world,ego,actors,c,a,previous,event)
                captured.update(observation=observation,participants=participants,body=body)
                return observation
            row=recording.tick(frame,time_s,measure)
            observation=captured['observation'];participants=captured['participants'];body=captured['body']
            values.append(row);measurements.append(observation);history.append({'time_s':time_s,'participants':participants})
            if c['mechanism']=='uturn':save_scalar('sight_distance.minimum_from_either_approach',time_s,min(entry['any_body_sight_horizon']['distance_m'] for entry in observation['st.sight_distance']['approaches']))
            if c['mechanism']=='following':
                save_scalar('subject_truck_width',time_s,2*ego.bounding_box.extent.y);save_scalar('lead_truck_width',time_s,2*lead.bounding_box.extent.y)
            if c['mechanism']=='reverse':
                save_scalar('backing_intersection_overlap',time_s,bool(observation['rel.occupies']['authored_intersection_overlap'] and observation['drv.backing']));save_scalar('backing_crosswalk_overlap',time_s,bool(any(observation['rel.occupies']['native_crosswalk_overlap']) and observation['drv.backing']))
            histories.write(json.dumps(history[-1])+'\n');footprints.write(json.dumps({'time_s':time_s,'vertices':body})+'\n')
            if collisions:result['physical_failure_flags'].append('collision');result['termination_reason']='collision';break
            if i==len(path)-1 and math.hypot(ego.get_location().x-path[-1][0],ego.get_location().y-path[-1][1])<2:result['maneuver_completed']=True;result['termination_reason']='route_complete';break
        else:result['termination_reason']='timeout'
        result['measured_values']={'frames':len(values),'observed_stationary_hold_s':stationary_hold,'collision_events':collisions}
        if not values:raise RuntimeError('live_measurement: no original recorded frames')
        result.update(recording.result_fields());result['recording_evidence'].append({'name':'authored_test_context','unit':'structured','reference':'context.json'})
        # Actual original-window summaries use a frozen engineering interval (5..10 seconds after recording starts).
        first,last=values[0]['time_s'],values[-1]['time_s'];start,end=first+5.,min(last,first+10.)
        if end<start:raise RuntimeError('live_measurement: maneuver did not supply frozen five-second approach evaluation window')
        scalar=[{'time_s':row['time_s'],'value':row['speed_mps']} for row in values];actual,window=summarize(scalar,start,end)
        if c['mechanism'] not in ('yield','uturn'):
            result['target_checks'].append(measured_target('commanded_approach_speed',a['commanded_approach_speed']['value'],actual,.22352,'mean original speed within frozen engineering approach window, not a legal tolerance','channels/kin.speed.jsonl'))
        result['realized_observables']['kin.speed']={'value':actual,'unit':'m/s','method':'original actor.get_velocity norm','time_window':'frozen recording-relative 5..10s','sample_window_s':window,'statistic':'mean','reference':'channels/kin.speed.jsonl'}
        if c['mechanism']=='following':
            samples=[{'time_s':row['time_s'],'value':obs['rel.surface_gap']} for row,obs in zip(values,measurements)];actual,window=summarize(samples,start,end);result['target_checks'].append(measured_target('commanded_surface_gap',a['commanded_surface_gap']['value'],actual,1.,'mean original world-body longitudinal gap','channels/rel.surface_gap.jsonl'))
            result['realized_observables']['rel.surface_gap']={'value':actual,'unit':'m','method':'world-space measured bounding box projections','time_window':'frozen recording-relative 5..10s','sample_window_s':window,'statistic':'mean','reference':'channels/rel.surface_gap.jsonl'}
        elif c['mechanism']=='yield':result['target_checks'].append(measured_target('yield_hold_s',a['yield_hold_s']['value'],stationary_hold,.15,'sum original frames below 0.05m/s at declared approach gate; engineering only',['channels/kin.speed.jsonl','setup.json']))
        elif c['mechanism']=='reverse':
            intersection=any(o['rel.occupies']['authored_intersection_overlap'] and o['drv.backing'] for o in measurements);crosswalk=any(any(o['rel.occupies']['native_crosswalk_overlap']) and o['drv.backing'] for o in measurements)
            desired_intersection='into_intersection_reverse' in case['case_id'];desired_crosswalk='over_crosswalk_reverse' in case['case_id']
            result['target_checks'].append(measured_target('intersection_overlap_while_backing',desired_intersection,intersection,0,'same-frame footprint polygon intersection and signed actual reverse velocity','channels/rel.occupies.jsonl'))
            result['target_checks'].append(measured_target('crosswalk_overlap_while_backing',desired_crosswalk,crosswalk,0,'same-frame native crosswalk polygon intersection and signed actual reverse velocity','channels/rel.occupies.jsonl'))
        elif c['mechanism']=='uturn':
            distances=[]
            for obs in measurements:
                vis=obs['st.sight_distance'];distances.append(min(x['any_body_sight_horizon']['distance_m'] for x in vis['approaches']))
            actual=min(distances);result['target_checks'].append(measured_target('requested_sight_distance',a['requested_sight_distance']['value'],actual,1.,'minimum original any-of-nine incoming body horizons over entire maneuver; preserve bounds/brackets','channels/st.sight_distance.jsonl'))
        for name,data in auxiliary.items():
            statistic='max' if name.startswith('backing_') else 'min'
            value,window=summarize(data['samples'],first,last,statistic)
            result['realized_observables'][name]={'value':value,'unit':'bool' if name.startswith('backing_') else 'm','method':c['measurement_definitions'][name]['method'],'time_window':'entire original execution','sample_window_s':window,'statistic':statistic,'reference':name+'.jsonl'}
        if any(not check['matched'] for check in result['target_checks']):result['physical_failure_flags'].append('target_mismatch')
    except BaseException as exc:
        result['termination_reason']='runtime_error:'+str(exc);result['physical_failure_flags'].append(type(exc).__name__)
        text=str(exc);category='external_asset' if text.startswith('external_asset:') or isinstance(exc,ImportError) else 'live_measurement'
        result['external_requirements'].append({'requirement':text,'category':category,'evidence':'retained attempt/result and original artifacts before failure','next_action':'Provide verified dependency/native asset or inspect retained physical measurements, repair cause at same frozen setting and rerun once','requires_live_execution':category=='live_measurement'})
    finally:
        errors=resources.close();result['cleanup_errors']=errors
        if errors:result['physical_failure_flags'].append('cleanup_failure')
        if recording:
            result.update(recording.result_fields())
            if not any(x.get('name')=='authored_test_context' for x in result['recording_evidence']):result['recording_evidence'].append({'name':'authored_test_context','unit':'structured','reference':'context.json'})
            if recording.close_errors:result['physical_failure_flags'].append('recording_close_failed')
        if not result['physical_failure_flags']:
            try:validate_output(out,result,case['recording_description']);success=True
            except BaseException as exc:result['physical_failure_flags'].append('output_contract:'+str(exc))
        result['status']='recorded' if success else 'diagnostic';(out/'result.json').write_text(json.dumps(result,indent=2))
    return 0 if success else 2

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int);p.add_argument('--case-id');p.add_argument('--include-baselines',action='store_true');args=p.parse_args()
    if args.check:static_check();return 0
    if not all((args.output_dir,args.host,args.port)):p.error('--output-dir, --host, --port required')
    return execute(args)
if __name__=='__main__':sys.exit(main())
