#!/usr/bin/env python3
"""Draft original-frame physical controller; no legal verdict or invented evidence."""
import argparse,json,math,pathlib,sys,signal,queue,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parent

sys.path.insert(0,str(ROOT))
from scenario import route,physical_sample,target_checks,footprint_gap

def speed(v): return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def command(position,yaw,velocity,path,target):
    closest=min(range(len(path)),key=lambda i:math.hypot(path[i][0]-position[0],path[i][1]-position[1]))
    goal=path[min(closest+4,len(path)-1)]
    error=(math.atan2(goal[1]-position[1],goal[0]-position[0])-math.radians(yaw)+math.pi)%(2*math.pi)-math.pi
    effort=.45*(target-velocity)
    return dict(throttle=max(0,min(.65,effort)),brake=max(0,min(1,-effort)),steer=max(-.8,min(.8,1.4*error)))
def build_road():
    tree=ET.parse(ROOT/'road-template.xodr');root=tree.getroot();root.find('header').set('name','partition1-draft')
    if json.loads((ROOT/'config.json').read_text())['mechanism']!='stop':
        for road in root.findall('road'):
            for tag in ('objects','signals'):
                node=road.find(tag)
                if node is not None: road.remove(node)
    if json.loads((ROOT/'config.json').read_text())['mechanism']=='lane_change':
        for road in root.findall('road'):
            if road.get('id') in ('1','2','11'):
                for section in road.findall('lanes/laneSection'):
                    left=section.find('left')
                    if left is not None:section.remove(left)
                    for mark in section.findall('center/lane/roadMark'):mark.set('color','white')
    return ET.tostring(root,encoding='unicode')
def check():
    c=json.loads((ROOT/'config.json').read_text());p=json.loads((ROOT/'proposals/cases.json').read_text())
    assert set(c['supported_case_ids'])=={x['case_id'] for x in p['cases']}
    assert len(c['path'])>10 and all(len(x)==2 for x in c['path'])
    assert all(math.dist(a,b)<4 for a,b in zip(c['path'],c['path'][1:]))
    assert len(ET.fromstring(build_road()).findall('road'))==6
    assert not any(x.get('expected_label') for x in p['sweep_specs'])
    for case in p['cases']:
        path=route(c,case);assert all(math.dist(a,b)<4 for a,b in zip(path,path[1:]))
    print('Offline configuration, road, route continuity and case checks passed; runtime unconfirmed')
def run(args):
    import carla
    c=json.loads((ROOT/'config.json').read_text());cases={x['case_id']:x for x in json.loads((ROOT/'proposals/cases.json').read_text())['cases']}
    case=cases[args.case_id or c['default_case_id']]
    c['path']=route(c,case)
    if case['target_type']=='baseline': raise ValueError('Baseline is definition-only; select a physical target case')
    out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():raise FileExistsError('Retain prior attempt; choose a fresh output directory')
    client=carla.Client(args.host,args.port);client.set_timeout(30)
    if client.get_client_version()!=client.get_server_version():raise RuntimeError('Client/server version mismatch')
    # Authored map loading requires the executor dedicated resource lease.
    world=client.generate_opendrive_world(build_road());old=world.get_settings();actors=[];cap=None;stop=[False];frames=0
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    result=dict(setup_confirmed=False,behavior_attempted=False,maneuver_completed=False,termination_reason='setup_failure',physical_failure_flags=[],measured_values={},target_checks=[],recording_description=c['recording_description'],recording_evidence=[],realized_observables={},trace_reference='trace.jsonl',video_references=[],video_frame_map_reference='video_frame_map.jsonl',requested_variable_assignments=case['variable_assignments'])
    streams=[];samples=[];others=[];halt_start=None;collisions=[];channel_streams={}
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        bp=world.get_blueprint_library().find('vehicle.tesla.model3');p=c['path'][0]
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=p[0],y=p[1],z=.5),carla.Rotation(yaw=0)));actors.append(ego)
        if c['law_id'].endswith(('127-3','253')):
            pos=ego.get_location();op=carla.Transform(carla.Location(x=pos.x+30 if c['law_id'].endswith('127-3') else 60,y=pos.y if c['law_id'].endswith('127-3') else -1.75,z=.5),carla.Rotation(yaw=0 if c['law_id'].endswith('127-3') else 180))
            other=world.spawn_actor(bp,op);actors.append(other);others.append(other)
        if case['variable_assignments'].get('commanded_signal',{}).get('value',False):ego.set_light_state(carla.VehicleLightState.RightBlinker)
        sys.path.insert(0,str(ROOT.parents[1]/'runtime/python'))
        from pipeline_capture import PipelineCapture
        (out/'config.json').write_text(json.dumps(c))
        cap=PipelineCapture(client,ego,out,case['case_id'],required_observations=c['required_atoms'])
        collision=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=ego);actors.append(collision)
        collision.listen(lambda event:collisions.append(dict(frame=event.frame,other_actor_id=event.other_actor.id)))
        cameras=[]
        for i,pose in enumerate(c['cameras']):
            cbp=world.get_blueprint_library().find('sensor.camera.rgb');cbp.set_attribute('image_size_x',str(pose['width']));cbp.set_attribute('image_size_y',str(pose['height']));cbp.set_attribute('sensor_tick','0.05')
            cam=world.spawn_actor(cbp,carla.Transform(carla.Location(x=pose['x'],z=pose['z']),carla.Rotation(pitch=pose['pitch'])),attach_to=ego);actors.append(cam);q=queue.Queue();cam.listen(q.put);cameras.append((cam,q,i));(out/('rgb'+str(i))).mkdir()
        fmap=(out/'video_frame_map.jsonl').open('x');streams.append(fmap)
        raw=(out/'kin.speed.jsonl').open('x');streams.append(raw)
        physical=(out/'physical_samples.jsonl').open('x');streams.append(physical)
        (out/'channels').mkdir()
        for channel in case['recording_description']['channels']:
            stream=(out/'channels'/(channel['name']+'.jsonl')).open('x');channel_streams[channel['name']]=stream;streams.append(stream)
        (out/'context.json').write_text(json.dumps({'authored_context':case['variable_assignments']['authored_context']['value']}))
        result['behavior_attempted']=True
        for tick in range(c['max_ticks']):
            if stop[0]:result['termination_reason']='signal';break
            t=ego.get_transform();v=speed(ego.get_velocity());target=case['variable_assignments']['commanded_approach_speed']['value']
            if c['mechanism']=='stop' and case['variable_assignments'].get('commanded_halt',{}).get('value') and halt_start!='released':
                target=min(target,math.sqrt(2*1.5*max(0,-14-t.location.x)))
                if v<.05 and t.location.x>-20:
                    if halt_start is None:halt_start=tick
                    elif tick-halt_start>=40:halt_start='released'
            if others:
                other=others[0];ov=speed(other.get_velocity());ot=5
                if c['law_id'].endswith('127-3'):
                    gap=footprint_gap(ego,other);desired=case['variable_assignments']['commanded_gap_m']['value'];target=max(0,min(8,5+.25*(gap-desired)));ot=5
                elif case['variable_assignments'].get('commanded_yield',{}).get('value') and other.get_location().x>-12 and t.location.x>-20:target=0
                other.apply_control(carla.VehicleControl(throttle=max(0,min(.6,.45*(ot-ov))),brake=max(0,min(1,.45*(ov-ot)))))
            control=command((t.location.x,t.location.y),t.rotation.yaw,v,c['path'],target);ego.apply_control(carla.VehicleControl(**control))
            frame=world.tick();snap=world.get_snapshot();time_s=snap.timestamp.elapsed_seconds
            cap.capture(frame,time_s,extra={'ego_lamp_bits':int(ego.get_light_state())})
            sample=physical_sample(ego,c['path'],others,world);sample['time_s']=time_s;samples.append(sample);physical.write(json.dumps(sample)+'\n')
            direct={'kin.position':sample['position_m'],'kin.heading':sample['heading_deg'],'kin.speed':sample['speed_mps'],'rel.surface_gap':sample['gap_m']}
            for name,stream in channel_streams.items():stream.write(json.dumps(dict(time_s=time_s,value=direct.get(name),missing_capability=None if name in direct else 'native atom projection not yet implemented; raw original evidence retained'))+'\n')
            for cam,q,i in cameras:
                im=q.get(timeout=15)
                while im.frame<frame:im=q.get(timeout=15)
                if im.frame!=frame:raise RuntimeError('Camera/frame mismatch')
                im.save_to_disk(str(out/('rgb'+str(i))/('%06d.png'%frames)))
            fmap.write(json.dumps(dict(video_frame=frames,carla_frame=frame,time_s=time_s))+'\n');raw.write(json.dumps(dict(time_s=time_s,value=speed(ego.get_velocity())))+'\n');frames+=1
            end=c['path'][-1]
            if math.hypot(t.location.x-end[0],t.location.y-end[1])<2:result['maneuver_completed']=True;result['termination_reason']='route_end';break
        else:result['termination_reason']='timeout'
        result['target_checks']=target_checks(case,samples)
        if collisions:result['physical_failure_flags'].append('collision')
        (out/'collisions.json').write_text(json.dumps(collisions))
        result['measured_values']={'captured_frames':frames,'maximum_route_error_m':max((s['route_error_m'] for s in samples),default=None)};result['recording_evidence']=[dict(name=x['name'],unit=x['unit'],reference='channels/'+x['name']+'.jsonl') for x in case['recording_description']['channels']]
        result['video_references']=[dict(path='rgb'+str(i),format='original RGB PNG sequence; primary encoded review video outstanding') for i in range(4)]
        result['physical_failure_flags'].append('mandatory_atom_streams_and_law_specific_setup_not_finalized')
    except Exception as exc:
        result['physical_failure_flags'].append(type(exc).__name__+': '+str(exc));result['termination_reason']='runtime_failure'
    finally:
        if cap is not None:
            try:cap.close(confirmed=False)
            except Exception as cleanup_error:result['physical_failure_flags'].append('capture_cleanup: '+str(cleanup_error))
        for stream in streams:stream.close()
        for actor in reversed(actors):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception as cleanup_error:result['physical_failure_flags'].append('actor_cleanup: '+str(cleanup_error))
        try:world.apply_settings(old)
        except Exception as cleanup_error:result['physical_failure_flags'].append('settings_restore: '+str(cleanup_error))
        (out/'result.json').write_text(json.dumps(result,indent=2))
    return 2 # Draft: missing setup/observation acceptance never counts as successful execution.
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--output-dir');ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=2000);ap.add_argument('--case-id');a=ap.parse_args()
    if a.check:check()
    elif not a.output_dir:ap.error('--output-dir required')
    else:sys.exit(run(a))
