"""Median-opening crossing implementation draft; all outcomes are measured.

The two main roadways are 20 m apart, so their crossings remain separate
regions. OpenDRIVE links explicitly join all straight-travel approaches.
No official controls are authored into this uncontrolled test construction.
"""
import json,math,queue,signal,sys
from pathlib import Path

def road_xml(ident,x,y,heading,length,pre=None,suc=None,junction=-1):
    link=''
    for tag,other in [('predecessor',pre),('successor',suc)]:
        if other is not None:
            kind,num,contact=other
            link+='<%s elementType="%s" elementId="%s"%s/>'%(tag,kind,num,'' if kind=='junction' else ' contactPoint="'+contact+'"')
    return ('<road name="road-%s" length="%s" id="%s" junction="%s"><link>%s</link><type s="0" type="rural"/><planView><geometry s="0" x="%s" y="%s" hdg="%s" length="%s"><line/></geometry></planView><elevationProfile/><lateralProfile/><lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.12"/></lane></center><right><lane id="-1" type="driving" level="false"><link><predecessor id="-1"/><successor id="-1"/></link><width sOffset="0" a="7" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.12"/></lane></right></laneSection></lanes></road>'%(ident,length,ident,junction,link,x,y,heading,length))

def build_crossing():
    # Main roadway travels east at y=-3.5; opposing roadway travels west at y=23.5.
    # Crossing road goes north on x=203.5 and crosses both separated roadways.
    roads=[road_xml(1,0,0,0,190,suc=('junction',10,'')),road_xml(2,210,0,0,390,pre=('junction',10,'')),road_xml(11,190,0,0,20,pre=('road',1,'end'),suc=('road',2,'start'),junction=10),
           road_xml(3,600,20,math.pi,390,suc=('junction',20,'')),road_xml(4,190,20,math.pi,190,pre=('junction',20,'')),road_xml(21,210,20,math.pi,20,pre=('road',3,'end'),suc=('road',4,'start'),junction=20),
           road_xml(5,200,-200,math.pi/2,193,suc=('junction',10,'')),road_xml(6,200,0,math.pi/2,20,pre=('junction',10,''),suc=('junction',20,'')),road_xml(7,200,27,math.pi/2,173,pre=('junction',20,'')),
           road_xml(12,200,-7,math.pi/2,7,pre=('road',5,'end'),suc=('road',6,'start'),junction=10),road_xml(22,200,20,math.pi/2,7,pre=('road',6,'end'),suc=('road',7,'start'),junction=20)]
    junctions=''
    for jid,connections in [(10,[(1,11),(5,12)]),(20,[(3,21),(6,22)])]:
        junctions+='<junction name="separate-crossing-%s" id="%s">'%(jid,jid)
        for i,(incoming,connecting) in enumerate(connections):junctions+='<connection id="%s" incomingRoad="%s" connectingRoad="%s" contactPoint="start"><laneLink from="-1" to="-1"/></connection>'%(i,incoming,connecting)
        junctions+='</junction>'
    return '<?xml version="1.0"?><OpenDRIVE><header revMajor="1" revMinor="4" name="median-crossings-draft" version="1" date="2026-10-27" north="0" south="0" east="0" west="0"/>'+''.join(roads)+junctions+'</OpenDRIVE>'

def footprint_in_region(vertices,region):
    # Axis-aligned rectangle overlap is conservative for a rotated footprint;
    # retain vertices so downstream exact polygon occupancy can check the bracket.
    xs=[v[0] for v in vertices];ys=[v[1] for v in vertices]
    x0,y0,x1,y1=region
    return min(xs)<=x1 and max(xs)>=x0 and min(ys)<=y1 and max(ys)>=y0

def entry_bracket(previous,current):
    if previous is not None and not previous['inside'] and current['inside']:
        return [previous['time_s'],current['time_s']]
    return None

def yield_target(branch,other_inside,other_has_entered,ego_front_x):
    return 0. if branch=='prior_entry_yield' and other_has_entered and other_inside and ego_front_x<200 else 8.

def finalization(samples,case):
    events={};previous={};entry={};exit={}
    for sample in samples:
        for role in ('ego','other'):
            item={'time_s':sample['time_s'],'inside':sample[role]['inside']}
            bracket=entry_bracket(previous.get(role),item)
            if bracket is not None and role not in entry:entry[role]=bracket
            if previous.get(role,{}).get('inside') and not item['inside']:exit[role]=[previous[role]['time_s'],item['time_s']]
            previous[role]=item
    if 'ego' in entry and 'other' in entry:
        # An order is confirmed only when retained uncertainty brackets do not overlap.
        earlier=entry['other'][1]<entry['ego'][0]
        precedence=exit.get('other',[float('inf'),float('inf')])[1]<entry['ego'][0]
    else:earlier=None;precedence=None
    events.update(entry_brackets_s=entry,exit_brackets_s=exit,other_entry_precedes_ego=earlier,ego_enters_after_other_clears=precedence)
    return events

def execute(args,cfg,case):
    from runner import speed_control,steering
    import carla
    root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'runtime/python'))
    from pipeline_capture import PipelineCapture
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    result={'case_id':case['case_id'],'requested_variable_assignments':case['variable_assignments'],'measured_values':{},'target_checks':[],'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'preflight','physical_failure_flags':[],'trace_reference':None,'video_references':[],'video_frame_map_reference':None,'recording_description':case['recording_description'],'recording_evidence':[],'realized_observables':{},'missing_capabilities':cfg['implementation_gaps']}
    owned=[];capture=None;world=None;settings=None;samples=[];stopped=[False]
    def stop(*unused):stopped[0]=True
    prior={s:signal.signal(s,stop) for s in (signal.SIGINT,signal.SIGTERM)}
    try:
        client=carla.Client(args.host,args.port);client.set_timeout(30.)
        if client.get_client_version()!=client.get_server_version():raise RuntimeError('Version mismatch')
        world=client.generate_opendrive_world(build_crossing(),carla.OpendriveGenerationParameters(vertex_distance=1.,max_road_length=50.,wall_height=0.,additional_width=.0,smooth_junctions=False,enable_mesh_visibility=True))
        settings=world.get_settings();active=world.get_settings();active.synchronous_mode=True;active.fixed_delta_seconds=.05;world.apply_settings(active)
        lib=world.get_blueprint_library();bp=lib.find('vehicle.tesla.model3')
        # Fixed comparison setup, distinct participant role/route only.
        ego=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=177,y=-3.5,z=.5),carla.Rotation(yaw=0)))
        if ego is None:raise RuntimeError('Ego spawn unavailable')
        owned.append(ego)
        other=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=203.5,y=-11,z=.5),carla.Rotation(yaw=90)))
        if other is None:raise RuntimeError('Other spawn unavailable')
        owned.append(other);cameras=[]
        for i,pose in enumerate(cfg['cameras']):
            camera_bp=lib.find('sensor.camera.rgb');camera_bp.set_attribute('image_size_x',str(pose['width']));camera_bp.set_attribute('image_size_y',str(pose['height']));camera_bp.set_attribute('sensor_tick','0.05')
            sensor=world.spawn_actor(camera_bp,carla.Transform(carla.Location(**pose['location']),carla.Rotation(**pose['rotation'])),attach_to=ego);owned.append(sensor);q=queue.Queue();sensor.listen(q.put);directory=out/('camera'+str(i));directory.mkdir();cameras.append((q,directory))
        (out/'config.json').write_text(json.dumps(cfg,indent=2));(out/'authored_geometry.json').write_text(json.dumps({'intersection_region':[200,-7,207,0],'opposite_crossing_region':[200,20,207,27],'median_strip':[0,0,600,20],'opening_x':[190,210],'highway_identity':['main_divided','crossing_highway'],'administrative_status':'synthetic test assumptions; no authority evidence','occupancy_method':'conservative AABB; all vertices retained'}))
        capture=PipelineCapture(client,ego,out,case['case_id'],required_observations=cfg['required_atoms'])
        entered=False;branch=case['variable_assignments']['test_branch']['value']
        raw=(out/'participants.jsonl').open('x');fmap=(out/'video_frame_map.jsonl').open('x')
        try:
            for step in range(600):
                if stopped[0]:result['termination_reason']='signal';break
                positions={};inside={};verts={}
                for role,actor in [('ego',ego),('other',other)]:
                    transform=actor.get_transform();verts[role]=[[v.x,v.y,v.z] for v in actor.bounding_box.get_world_vertices(transform)];inside[role]=footprint_in_region(verts[role],[200,-7,207,0]);positions[role]=transform
                entered=entered or inside['other'];front=max(v[0] for v in verts['ego']);targets={'ego':yield_target(branch,inside['other'],entered,front),'other':3.}
                if 'requested_arrival_offset_s' in cfg:
                    elapsed=step*.05;offset=cfg['requested_arrival_offset_s']
                    targets={'ego':0. if elapsed<max(0.,offset) else 8.,'other':0. if elapsed<max(0.,-offset) else 3.}
                for role,actor in [('ego',ego),('other',other)]:
                    v=actor.get_velocity();actual=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z);throttle,brake=speed_control(targets[role],actual);t=positions[role];target=(400,-3.5) if role=='ego' else (203.5,100)
                    actor.apply_control(carla.VehicleControl(throttle=throttle,brake=brake,steer=steering((t.location.x,t.location.y),math.radians(t.rotation.yaw),target)))
                frame=world.tick();snap=world.get_snapshot();time_s=snap.timestamp.elapsed_seconds;capture.capture(frame,time_s)
                sample={'time_s':time_s,'carla_frame':frame}
                for role,actor in [('ego',ego),('other',other)]:
                    t=actor.get_transform();v=actor.get_velocity();vertices=[[p.x,p.y,p.z] for p in actor.bounding_box.get_world_vertices(t)]
                    sample[role]={'position':[t.location.x,t.location.y,t.location.z],'heading_deg':t.rotation.yaw,'speed_mps':math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z),'vertices':vertices,'inside':footprint_in_region(vertices,[200,-7,207,0]),'requested_speed_mps':targets[role]}
                samples.append(sample);raw.write(json.dumps(sample)+'\n')
                for q,directory in cameras:
                    image=q.get(timeout=10.)
                    if image.frame!=frame:raise RuntimeError('Camera frame mismatch')
                    image.save_to_disk(str(directory/('%06d.png'%step)))
                fmap.write(json.dumps({'video_frame':step,'carla_frame':frame,'time_s':time_s})+'\n');result['behavior_attempted']=True
                if sample['ego']['position'][0]>230 and sample['other']['position'][1]>12:
                    result['maneuver_completed']=True;result['termination_reason']='both_passed_crossing';break
            else:result['termination_reason']='30s_timeout'
        finally:raw.close();fmap.close()
        measured=finalization(samples,case);result['measured_values']=measured
        result['target_checks']=[{'target':'other_entry_precedes_ego','requested':True,'measured':measured['other_entry_precedes_ego'],'method':'nonoverlapping full-footprint AABB entry sample brackets; exact vertices retained','tolerance':'one 0.05s bracket per event','matched':measured['other_entry_precedes_ego'] is True,'physical_cause_confirmed':False,'cause_evidence':['authored_geometry.json','road.xodr','participants.jsonl','capture/native']}]
        result['trace_reference']='trace.jsonl';result['video_references']=['camera'+str(i) for i in range(4)];result['video_frame_map_reference']='video_frame_map.jsonl'
        result['recording_evidence']=[{'name':'participants','unit':'m,m/s,s','reference':'participants.jsonl'}]
        # Target-specific capture is real, but mandatory atom completeness and rendered
        # median facts must still be independently validated before ready delivery.
        result['physical_failure_flags'].append('incomplete_mandatory_atom_and_physical_median_validation')
    except Exception as exc:result['termination_reason']=str(exc);result['physical_failure_flags'].append('setup_or_capture_failure')
    finally:
        if capture is not None:capture.close(confirmed=False)
        for actor in reversed(owned):
            if hasattr(actor,'stop'):actor.stop()
            actor.destroy()
        if world is not None and settings is not None:world.apply_settings(settings)
        for sig,handler in prior.items():signal.signal(sig,handler)
        with (out/'result.json').open('x') as stream:json.dump(result,stream,indent=2)
    return 2
