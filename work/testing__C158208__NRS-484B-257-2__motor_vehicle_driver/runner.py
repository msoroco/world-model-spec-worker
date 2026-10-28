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

def execute(args):
    c=load();case=next(i for i in c['cases'] if i['case_id']==(args.case_id or c['selected_case_id']))
    if case['target_type']=='baseline' and not args.include_baselines:raise ValueError('Baseline is not selected by default; explicit --include-baselines required')
    out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    # Exclusive outputs; an existing executor-created directory is supported.
    reservation=(out/'attempt.json').open('x');reservation.write(json.dumps({'case_id':case['case_id']}));reservation.close()
    import carla
    sys.path.insert(0,str(ROOT.parents[1]/'runtime/python'))
    from pipeline_capture import PipelineCapture
    client=carla.Client(args.host,args.port);client.set_timeout(30)
    if client.get_client_version()!=client.get_server_version(): raise RuntimeError('CARLA client/server version mismatch')
    world=client.generate_opendrive_world((ROOT/'road.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=1.,max_road_length=50.,wall_height=0.,additional_width=.2,smooth_junctions=True,enable_mesh_visibility=True))
    old=world.get_settings();actors=[];sensors=[];capture=None;streams={};flag={'stop':False};old_handlers={};result=None;frame_map=None;lead_path=None;lead_index=0
    result={'case_id':case['case_id'],'status':'draft','requested_variable_assignments':case['variable_assignments'],'measured_values':{},'target_checks':[],'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'initialization','physical_failure_flags':[],'trace_reference':'trace.jsonl','video_references':[],'video_frame_map_reference':'video-frame-map.jsonl','recording_description':case['recording_description'],'recording_evidence':[],'realized_observables':{},'runtime_uncertainties':c['delivery_gaps']}
    def stop(signum,frame):flag['stop']=True
    try:
        for sig in (signal.SIGINT,signal.SIGTERM):old_handlers[sig]=signal.signal(sig,stop)
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/c['hz'];world.apply_settings(settings)
        path=route(world,c,case);a=case['variable_assignments'];reverse=c['mechanism']=='reverse'
        bp=world.get_blueprint_library().find(c['vehicle_blueprint']);bp.set_attribute('role_name','subject')
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(*path[0]),carla.Rotation(yaw=0.)));actors.append(ego)
        lead=None
        if c['mechanism']=='following':
            width=ego.bounding_box.extent.y*2
            if width<2.032:raise RuntimeError('Subject truck width below statutory 80-inch qualifying class')
            gap=a['commanded_surface_gap']['value'];p=path[0]
            lead=world.spawn_actor(bp,carla.Transform(carla.Location(p[0]+gap+ego.bounding_box.extent.x*2,p[1],p[2]),carla.Rotation()));actors.append(lead)
            if lead.bounding_box.extent.y*2<2.032:raise RuntimeError('Lead truck width below statutory qualifying class')
        if c['mechanism']=='yield':
            # Cross participant uses actual native cross-road lane; no officer/signal invented.
            w=world.get_map().get_waypoint_xodr(3,-1,480.)
            if w is None:raise RuntimeError('Cross road unavailable')
            t=w.transform;t.location.z+=.35;lead=world.spawn_actor(world.get_blueprint_library().find('vehicle.lincoln.mkz_2020'),t);actors.append(lead)
            lead_path=[]
            for road,stations in ((3,range(480,490,2)),(21,range(0,20,2)),(4,range(0,200,2))):
                for station in stations:
                    waypoint=world.get_map().get_waypoint_xodr(road,-1,float(station))
                    if waypoint is None:raise RuntimeError('Native cross-participant route missing')
                    location=waypoint.transform.location;lead_path.append([location.x,location.y,location.z+.35])
        # No rendered-sign/crosswalk claim is made from OpenDRIVE metadata alone.
        result['setup_confirmed']=False
        image_queues=[]
        for idx,cam in enumerate(c['cameras']):
            cb=world.get_blueprint_library().find('sensor.camera.rgb');cb.set_attribute('image_size_x',str(cam['width']));cb.set_attribute('image_size_y',str(cam['height']));cb.set_attribute('fov',str(cam['fov']));cb.set_attribute('sensor_tick','0')
            sensor=world.spawn_actor(cb,carla.Transform(carla.Location(*cam['location']),carla.Rotation(pitch=cam['pitch'])),attach_to=ego);actors.append(sensor);sensors.append(sensor);q=queue.Queue();sensor.listen(q.put);image_queues.append(q);(out/('camera-'+str(idx))).mkdir(exist_ok=False)
        put_config=dict(c,selected_case_id=case['case_id']);(out/'config.json').write_text(json.dumps(put_config,indent=2))
        capture=PipelineCapture(client,ego,out,case['case_id'],required_observations=[o['name'] for o in c['observations']])
        for channel in case['recording_description']['channels']:
            name=channel['name'];streams[name]=(out/('channel-'+name.replace('.','_')+'.jsonl')).open('x')
            result['recording_evidence'].append({'name':name,'unit':channel['unit'],'reference':'channel-'+name.replace('.','_')+'.jsonl'})
        frame_map=(out/'video-frame-map.jsonl').open('x');context={'authored_test_context':a,'provenance':'draft authored facts; native physical realization unverified'};(out/'context.json').write_text(json.dumps(context,indent=2))
        i=0;rows=[];gap_values=[];yield_hold_started=None
        for tick in range(int(c['duration_s']*c['hz'])):
            if flag['stop']:result['termination_reason']='signal';break
            t=ego.get_transform();v=speed(ego.get_velocity());target=a['commanded_approach_speed']['value']
            if c['mechanism']=='yield' and t.location.x>475:
                if yield_hold_started is None:yield_hold_started=tick/c['hz']
                if tick/c['hz']-yield_hold_started<a['yield_hold_s']['value']:target=0.
            if c['mechanism']=='following' and lead is not None:
                gap=surface_gap(ego,lead);gap_values.append(gap);target=max(0.,min(12.,target+.15*(gap-a['commanded_surface_gap']['value'])))
                lead.apply_control(carla.VehicleControl(throttle=max(0.,min(.7,.3*(a['commanded_approach_speed']['value']-speed(lead.get_velocity()))))))
            ctl,i=command((t.location.x,t.location.y),math.radians(t.rotation.yaw),v,path,i,target,reverse)
            ego.apply_control(carla.VehicleControl(**ctl));result['behavior_attempted']=True
            if c['mechanism']=='yield' and lead is not None:
                lt=lead.get_transform();lv=speed(lead.get_velocity())
                lead_target=4. if lead_index<len(lead_path)-1 else 0.
                lead_control,lead_index=command((lt.location.x,lt.location.y),math.radians(lt.rotation.yaw),lv,lead_path,lead_index,lead_target)
                lead.apply_control(carla.VehicleControl(**lead_control))
            frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds;row=capture.capture(frame,time_s);rows.append(row)
            frame_map.write(json.dumps({'video_frame':tick,'carla_frame':frame,'time_s':time_s})+'\n')
            for ci,q in enumerate(image_queues):
                image=q.get(timeout=20.)
                while image.frame<frame:image=q.get(timeout=20.)
                if image.frame!=frame:raise RuntimeError('Camera/trace frame mismatch')
                image.save_to_disk(str(out/('camera-'+str(ci))/('%06d.png'%tick)))
            # Directly measured channels only. All unsupported atoms remain null with explicit missing capability.
            measured={'kin.position':row['position'],'kin.heading':row['heading_deg'],'kin.speed':row['speed_mps'],'kin.extent':{'subject_width_m':2*ego.bounding_box.extent.y},'rel.surface_gap':surface_gap(ego,lead) if c['mechanism']=='following' else None,'drv.backing':bool(ego.get_control().reverse and row['speed_mps']>.01)}
            for name,stream in streams.items():stream.write(json.dumps({'time_s':time_s,'value':measured.get(name),'missing_capability':None if name in measured else 'Requires original graph/geometry evidence projection; not substituted from target'})+'\n')
            if i==len(path)-1 and math.hypot(t.location.x-path[-1][0],t.location.y-path[-1][1])<2:result['maneuver_completed']=True;result['termination_reason']='route_complete';break
        else:result['termination_reason']='timeout'
        frame_map.close();result['measured_values']={'last_speed_mps':rows[-1]['speed_mps'] if rows else None,'surface_gap_samples':gap_values,'frames':len(rows)}
        result['physical_failure_flags']=['mandatory_observation_projection_incomplete','native_setup_not_confirmed','review_video_not_encoded']
        for target in ('commanded_approach_speed','commanded_surface_gap','requested_sight_distance'):
            if target not in a:continue
            values=[r['speed_mps'] for r in rows] if target=='commanded_approach_speed' else gap_values if target=='commanded_surface_gap' else []
            result['target_checks'].append({'target':target,'requested':a[target]['value'],'measured':sum(values)/len(values) if values else None,'method':'mean of original samples; full trace retained','tolerance':.22352 if target=='commanded_approach_speed' else 1.,'matched':False,'physical_cause_confirmed':False,'cause_evidence':'capture/evidence.jsonl; requires measured finalization'})
        result['video_references']=[{'path':'camera-'+str(j),'format':'original RGB PNG sequence','encoded_review_video':False} for j in range(4)]
    except BaseException as exc:
        result['termination_reason']='runtime_error:'+str(exc);result['physical_failure_flags'].append(type(exc).__name__)
        raise
    finally:
        cleanup_resources(capture,streams,sensors,actors,world,old,old_handlers,result,out,frame_map)
    return 0 if result['setup_confirmed'] and result['maneuver_completed'] and not result['physical_failure_flags'] else 2

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int);p.add_argument('--case-id');p.add_argument('--include-baselines',action='store_true');args=p.parse_args()
    if args.check:static_check();return 0
    if not all((args.output_dir,args.host,args.port)):p.error('--output-dir, --host, --port required')
    return execute(args)
if __name__=='__main__':sys.exit(main())
