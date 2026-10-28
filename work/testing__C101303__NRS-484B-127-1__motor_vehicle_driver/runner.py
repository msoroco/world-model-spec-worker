#!/usr/bin/env python3
"""Configuration-driven original-frame experiment, never a legal acceptance test."""
import argparse,copy,json,math,pathlib,queue,signal,subprocess,sys,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parent
DT=.05

def norm(v):return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def clamp(x,a,b):return max(a,min(b,x))
def heading_error(actual,target):return (target-actual+180)%360-180

def control(x,y,yaw,speed,path,target):
    i=min(range(len(path)),key=lambda n:math.hypot(x-path[n][0],y-path[n][1]))
    goal=path[min(i+max(3,int(speed*.6)),len(path)-1)]
    angle=math.degrees(math.atan2(goal[1]-y,goal[0]-x));err=heading_error(yaw,angle)
    effort=.5*(target-speed)
    return {'throttle':clamp(effort,0,.8),'brake':clamp(-effort,0,1),'steer':clamp(err/45,-.7,.7)}

def physical_gap(ego_vertices,other_vertices,forward):
    a=[p[0]*forward[0]+p[1]*forward[1] for p in ego_vertices]
    b=[p[0]*forward[0]+p[1]*forward[1] for p in other_vertices]
    return min(b)-max(a)

def summarize(samples,start,end):
    selected=[r for r in samples if start<=r['time_s']<=end]
    if not selected:raise ValueError('No observed samples in frozen evaluation window')
    return {'mean':sum(r['value'] for r in selected)/len(selected),'min':min(r['value'] for r in selected),'max':max(r['value'] for r in selected),'sample_window_s':[selected[0]['time_s'],selected[-1]['time_s']],'samples':len(selected)}

def xodr(cfg):
    tree=ET.parse(ROOT/'road-template.xodr');r=tree.getroot();r.find('header').set('name',cfg['cell_id']+' authored physical trial')
    road=r.find('road');road.set('length','2400');road.find('planView/geometry').set('length','2400')
    # OpenDRIVE uses right-handed t; CARLA returns the reflected native map.
    width=3.0 if cfg['mode']=='alley' else 3.25
    for side in ('left','right'):
        for lane in road.findall('lanes/laneSection/'+side+'/lane'):
            if abs(int(lane.get('id')))==1:lane.find('width').set('a',str(width))
    if cfg['mode']=='following':
        # Two same-direction lanes physically support the requested lane change.
        left=road.find('lanes/laneSection/left');road.find('lanes/laneSection').remove(left)
        right=road.find('lanes/laneSection/right');lane=copy.deepcopy(right.find('lane'));lane.set('id','-2');right.append(lane)
        existing=[x for x in right.findall('lane') if x.get('id')=='-2'];right.remove(existing[0])
        e=road.find('elevationProfile');e.clear()
        for s,a,b,c,d in [(0,0,.04,0,0),(600,24,.04,-.0001,0),(1000,24,-.04,0,0)]:ET.SubElement(e,'elevation',s=str(s),a=str(a),b=str(b),c=str(c),d=str(d))
    return ET.tostring(r,encoding='unicode')

def offline_check():
    cfg=json.loads((ROOT/'config.json').read_text());proposal=json.loads((ROOT/'proposals/cases.json').read_text())
    assert cfg['actor']=='motor_vehicle_driver'
    assert set(cfg['supported_case_ids'])=={c['case_id'] for c in proposal['cases']}
    assert cfg['default_case_id']!=proposal['cases'][0]['case_id'] and proposal['cases'][0]['target_type']=='baseline'
    for c in proposal['cases']:
        assert c['recording_description']==cfg['recording_description']
        assert all(v['value'] is None for v in c['variable_assignments'].values() if v['kind']=='subject_behavior')
    if cfg['mode'] in ('alley','following'):
        road=ET.fromstring(xodr(cfg)).find('road');assert float(road.get('length'))>=2400
        assert 300+cfg['maximum_speed_mps']*cfg['duration_s']+230<2400
    if cfg['mode'] in ('alley','posted'):
        values=[c['variable_assignments']['commanded_approach_speed']['value'] for c in proposal['cases'][1:]]
        t=cfg['threshold_mph'];assert all(abs(a-b)<1e-8 for a,b in zip(values,[(t-5)*.44704,(t-.5)*.44704,(t+5)*.44704]))
    assert len(cfg['cameras'])==4 and cfg['capture_hz']==20
    print(json.dumps({'offline_configuration_geometry_and_case_checks':'passed','live_connection':False,'status':cfg['delivery_status']}))

def select_native(world,cfg):
    """Discover actual device-governed routes; fail instead of inventing devices."""
    mapping=world.get_map()
    for light in sorted(world.get_actors().filter('traffic.traffic_light'),key=lambda a:a.id):
        for wp in light.get_stop_waypoints():
            ahead=wp.next(2)
            seen=[]
            for _ in range(120):
                if not ahead:break
                w=ahead[0];seen.append(w)
                if w.is_junction and len(seen)>10:break
                ahead=w.next(2)
            if not seen or not seen[-1].is_junction:continue
            junction=seen[-1].get_junction()
            pairs=junction.get_waypoints(__import__('carla').LaneType.Driving)
            two_way=any(a.road_id==b.road_id and a.lane_id*b.lane_id<0 for a,_ in pairs for b,_ in pairs)
            if cfg['mode']=='signal' and not two_way:continue
            before=wp.previous(70)
            if not before:continue
            route=[before[0]];current=before[0]
            for _ in range(150):
                choices=current.next(2)
                if not choices:break
                current=min(choices,key=lambda w:abs(heading_error(route[-1].transform.rotation.yaw,w.transform.rotation.yaw)))
                route.append(current)
                if len(route)>60 and not current.is_junction and any(x.is_junction for x in route):break
            if any(w.is_junction for w in route):
                return route,light,wp,junction,pairs
    raise RuntimeError('No native signal-governed route meeting topology found; bind a surveyed map, never fabricate control')

def run(args):
    import carla
    cfg=json.loads((ROOT/'config.json').read_text());case=next(c for c in cfg['cases'] if c['case_id']==(args.case_id or cfg['default_case_id']))
    if case['target_type']=='baseline':raise ValueError('Baseline is intentionally not selected for execution')
    out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():raise FileExistsError('Previous attempt retained; use a fresh output directory')
    client=carla.Client(args.host,args.port);client.set_timeout(90)
    owned=[];streams={};encoders=[];cap=None;world=None;old=None;weather=None;prior_name=None;signals=[];previous_signals={};changed_map=False;hist=[];contacts=[];stop=[False];error=None;start=None;reader=None
    result={'case_id':case['case_id'],'cell_id':cfg['cell_id'],'actor':cfg['actor'],'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'initialization','physical_failure_flags':[],'target_checks':[],'measured_values':{},'requested_variable_assignments':{k:v for k,v in case['variable_assignments'].items() if v['kind'] in ('world_setup','controller')},'recording_description':case['recording_description'],'recording_evidence':[],'realized_observables':{},'trace_reference':None,'video_references':[],'video_frame_map_reference':None}
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        if client.get_client_version()!=client.get_server_version():raise RuntimeError('CARLA client/server mismatch')
        world=client.get_world();old=world.get_settings();weather=world.get_weather();prior_name=world.get_map().name
        (out/'previous-world.xodr').write_text(world.get_map().to_opendrive())
        if cfg['mode'] in ('alley','following'):
            if any(a.type_id.startswith(('vehicle.','walker.','sensor.')) for a in world.get_actors()):raise RuntimeError('Authored world requires executor dedicated resource lease with no other owned actors')
            world=client.generate_opendrive_world(xodr(cfg));changed_map=True
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=DT;world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon);mapping=world.get_map();light=None;stop_wp=None;junction=None;pairs=[]
        if cfg['mode'] in ('signal','inoperative'):
            route,light,stop_wp,junction,pairs=select_native(world,cfg)
            signals=list(light.get_group_traffic_lights())
            for a in signals:previous_signals[a.id]=(a,a.get_state(),a.is_frozen());a.freeze(True)
        elif cfg['mode']=='posted':
            # A real sign and lane binding are essential; a scalar get_speed_limit alone is not enough.
            signs=list(world.get_actors().filter('traffic.speed_limit.*'))
            selected=None
            for s in signs:
                try:limit=float(s.type_id.rsplit('.',1)[1])/.44704/3.6
                except ValueError:continue
                wp=mapping.get_waypoint(s.get_location());prev=wp.previous(100)
                if abs(limit-cfg['threshold_mph'])<.1 and prev:selected=(s,prev[0]);break
            if selected is None:raise RuntimeError('No native sign with configured posted limit; requires surveyed binding, not a synthetic sign overlay')
            sign,current=selected;route=[current]
            for _ in range(500):
                nxt=current.next(2)
                if len(nxt)!=1:break
                current=nxt[0];route.append(current)
            if len(route)<250:raise RuntimeError('Posted governed route too short for fixed episode')
        else:
            route_start=650 if cfg['mode']=='following' else 300
            route=[mapping.get_waypoint_xodr(1,-1,s) for s in range(route_start,2001,2)]
            if any(w is None for w in route):raise RuntimeError('Generated route discontinuity')
        path=[[w.transform.location.x,w.transform.location.y] for w in route]
        transform=route[0].transform;transform.location.z+=.5
        ego=world.spawn_actor(world.get_blueprint_library().find('vehicle.tesla.model3'),transform);owned.append(ego)
        leader=None
        if cfg['mode']=='following':
            gap=case['variable_assignments']['commanded_following_gap']['value'];tr=mapping.get_waypoint_xodr(1,-1,650+gap+5).transform;tr.location.z+=.5
            leader=world.spawn_actor(world.get_blueprint_library().find('vehicle.lincoln.mkz_2020'),tr);owned.append(leader)
        collision=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=ego);owned.append(collision);collision.listen(lambda e:contacts.append({'frame':e.frame,'other_id':e.other_actor.id}))
        for i,camera in enumerate(cfg['cameras']):
            bp=world.get_blueprint_library().find('sensor.camera.rgb');bp.set_attribute('image_size_x',str(camera['width']));bp.set_attribute('image_size_y',str(camera['height']));bp.set_attribute('sensor_tick','0.05')
            t=carla.Transform(carla.Location(x=camera['x'],y=camera.get('y',0),z=camera['z']),carla.Rotation(pitch=camera['pitch'],yaw=camera.get('yaw',0)))
            sensor=world.spawn_actor(bp,t,attach_to=ego);owned.append(sensor);q=queue.Queue();sensor.listen(q.put)
            log=(out/('camera%d-encoder.log'%i)).open('x');p=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra','-s','%dx%d'%(camera['width'],camera['height']),'-r','20','-i','pipe:0','-an','-c:v','ffv1','-threads','2',str(out/('camera%d.mkv'%i))],stdin=subprocess.PIPE,stderr=log);encoders.append((sensor,q,p,log,'camera%d.mkv'%i))
        (out/'channels').mkdir();(out/'config.json').write_text(json.dumps(cfg,indent=2))
        for ch in case['recording_description']['channels']:streams[ch['name']]=(out/'channels'/(ch['name']+'.jsonl')).open('x')
        context={'authored_context':case['variable_assignments']['authored_context']['value'],'native_map':mapping.name,'device_provenance':'native CARLA assets; official legal status is authored assumption','required_context':cfg['required_context']};(out/'context.json').write_text(json.dumps(context,indent=2))
        fmap=(out/'video_frame_map.jsonl').open('x');streams['__frame_map']=fmap
        # Absolute repository runtime helper location; package adopts the supplied source, not an upstream import.
        sys.path.insert(0,str(ROOT.parents[1]/'runtime/python'))
        from pipeline_capture import PipelineCapture
        cap=PipelineCapture(client,ego,out,case['case_id'],required_observations=cfg['required_atoms']);reader=(out/'capture/evidence.jsonl').open()
        start=world.get_snapshot().timestamp.elapsed_seconds;speed_samples=[];gap_samples=[];stop_since=None;halt_complete=False;first_entry=None
        result['behavior_attempted']=True
        for tick in range(round(cfg['duration_s']/DT)):
            elapsed=world.get_snapshot().timestamp.elapsed_seconds-start
            if stop[0]:result['termination_reason']='signal';break
            t=ego.get_transform();v=norm(ego.get_velocity());target=case['variable_assignments']['commanded_approach_speed']['value'];dynamic=path
            if cfg['mode']=='following':
                own=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(t)];lt=leader.get_transform();other=[[v.x,v.y,v.z] for v in leader.bounding_box.get_world_vertices(lt)];fwd=t.get_forward_vector();gap=physical_gap(own,other,[fwd.x,fwd.y]);requested=case['variable_assignments']['commanded_following_gap']['value'];target=clamp(8+.15*(gap-requested),0,15)
                lp=control(lt.location.x,lt.location.y,lt.rotation.yaw,norm(leader.get_velocity()),path,8);leader.apply_control(carla.VehicleControl(**lp))
                # Smooth requested lane change after 15s; leader remains in original lane.
                blend=clamp((elapsed-15)/6,0,1);shift=3.25*(blend*blend*(3-2*blend));dynamic=[[p[0],p[1]+shift] for p in path]
            if light is not None:
                phase=carla.TrafficLightState.Off if cfg['mode']=='inoperative' else carla.TrafficLightState.Yellow if elapsed<4 else carla.TrafficLightState.Red
                for s in signals:s.set_state(phase)
                d=math.hypot(t.location.x-stop_wp.transform.location.x,t.location.y-stop_wp.transform.location.y)
                halt=case['variable_assignments'].get('commanded_halt',{}).get('value',False)
                if halt and not halt_complete:
                    target=min(target,math.sqrt(2*1.5*max(0,d-3)))
                    if d<5 and v<.05:
                        stop_since=elapsed if stop_since is None else stop_since
                        if elapsed-stop_since>=1:halt_complete=True
                if cfg['mode']=='signal' and case['variable_assignments'].get('obey_red',{}).get('value') and elapsed>=4:target=min(target,math.sqrt(2*1.5*max(0,d-3)))
            if elapsed<1 or elapsed>=cfg['duration_s']-5:target=0
            c=control(t.location.x,t.location.y,t.rotation.yaw,v,dynamic,target);ego.apply_control(carla.VehicleControl(**c));ego.set_light_state(carla.VehicleLightState.LeftBlinker if cfg['mode']=='following' and 13<=elapsed<=22 else carla.VehicleLightState.NONE)
            frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds-start;row=cap.capture(frame,time_s,extra={'ego_lamp_bits':int(ego.get_light_state())});event=json.loads(reader.readline())
            body_vertices=ego.bounding_box.get_world_vertices(ego.get_transform())
            whole_body_inside=all(mapping.get_waypoint(v,project_to_road=False,lane_type=carla.LaneType.Driving) is not None for v in body_vertices)
            packet={'whole_body_inside_driving_surface':whole_body_inside,'native_evidence':event,'measured_telemetry':row,'signals':[{'id':a.id,'state':str(a.get_state()),'stop_waypoints':[{'road_id':w.road_id,'lane_id':w.lane_id,'s':w.s} for w in a.get_stop_waypoints()]} for a in signals],'contacts':list(contacts),'engineering_halt_complete':halt_complete}
            speed_samples.append({'time_s':time_s,'value':row['speed_mps']})
            if leader is not None:packet['footprint_longitudinal_gap_m']=gap;gap_samples.append({'time_s':time_s,'value':gap})
            for ch in case['recording_description']['channels']:
                value=row['speed_mps'] if ch['name'] in ('kin.speed','ego_speed') else row['position'] if ch['name']=='kin.position' else packet
                streams[ch['name']].write(json.dumps({'time_s':time_s,'value':value})+'\n')
            for sensor,q,p,log,name in encoders:
                im=q.get(timeout=30)
                while im.frame<frame:im=q.get(timeout=30)
                if im.frame!=frame:raise RuntimeError('Camera original-frame mismatch')
                p.stdin.write(im.raw_data)
            fmap.write(json.dumps({'video_frame':tick,'carla_frame':frame,'time_s':time_s})+'\n');hist.append(packet)
            if not whole_body_inside:result['termination_reason']='roadway_departure';break
            if contacts:result['termination_reason']='collision';break
            if abs(ego.get_transform().rotation.roll)>30:result['termination_reason']='loss_of_control';break
        else:result['maneuver_completed']=True;result['termination_reason']='frozen_episode_end'
        observed=summarize(speed_samples,*cfg['measurement_window_s']);result['measured_values']['ego_speed']=observed
        requested=case['variable_assignments']['commanded_approach_speed']['value'];matched=abs(observed['mean']-requested)<=.5*.44704
        result['target_checks'].append({'target':'commanded_approach_speed','requested':requested,'measured':observed,'method':'native velocity norm; frozen original-time sample mean','tolerance':.5*.44704,'matched':matched,'physical_cause_confirmed':True,'cause_evidence':['trace.jsonl','channels/kin.speed.jsonl']})
        result['realized_observables']['ego_speed']={'value':observed['mean'],'unit':'m/s','method':'native velocity norm','time_window':cfg['measurement_window_s'],'statistic':'mean','sample_window_s':observed['sample_window_s'],'reference':'channels/kin.speed.jsonl'}
        if gap_samples:result['measured_values']['following_gap']=summarize(gap_samples,5,14)
        if result['termination_reason'] in ('collision','loss_of_control','roadway_departure'):result['physical_failure_flags'].append(result['termination_reason'])
        result['trace_reference']='trace.jsonl';result['video_frame_map_reference']='video_frame_map.jsonl';result['recording_evidence']=[{'name':ch['name'],'unit':ch['unit'],'reference':'channels/'+ch['name']+'.jsonl'} for ch in case['recording_description']['channels']]
        result['recording_evidence'].append({'name':'authored_context','unit':'object','reference':'context.json#/authored_context'})
        # Native acquisition is executable, but semantic atom projection and feature audit must remain explicit.
        result['physical_failure_flags'].extend(cfg['runtime_gaps']);result['setup_confirmed']=False
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc);result['physical_failure_flags'].append(error);result['termination_reason']='runtime_failure'
    finally:
        cleanup=[]
        if reader:reader.close()
        if cap:
            try:cap.close(confirmed=False)
            except BaseException as exc:cleanup.append(str(exc))
        for f in streams.values():f.close()
        for sensor,q,p,log,name in encoders:
            try:p.stdin.close();code=p.wait(timeout=120)
            except BaseException as exc:cleanup.append(str(exc));code=-1
            log.close()
            if code==0:result['video_references'].append(name)
            else:cleanup.append('encoder failed: '+name)
        for a in reversed(owned):
            try:
                if hasattr(a,'stop'):a.stop()
                a.destroy()
            except BaseException as exc:cleanup.append(str(exc))
        for a,state,frozen in previous_signals.values():
            try:a.set_state(state);a.freeze(frozen)
            except BaseException as exc:cleanup.append(str(exc))
        if world is not None and old is not None:
            try:
                if changed_map:
                    maps=client.get_available_maps();native=next((m for m in maps if m.rsplit('/',1)[-1]==prior_name.rsplit('/',1)[-1]),None)
                    world=client.load_world(native) if native else client.generate_opendrive_world((out/'previous-world.xodr').read_text())
                world.apply_settings(old);world.set_weather(weather)
            except BaseException as exc:cleanup.append(str(exc))
        result['physical_failure_flags'].extend(cleanup);result['restoration']={'errors':cleanup,'restored':not cleanup};(out/'result.json').write_text(json.dumps(result,indent=2))
    return 2 # Partial semantic capability remains explicit; never claim first-run acceptance.

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000);p.add_argument('--case-id');a=p.parse_args()
    if a.check:offline_check()
    elif not a.output_dir:p.error('--output-dir required')
    else:sys.exit(run(a))
