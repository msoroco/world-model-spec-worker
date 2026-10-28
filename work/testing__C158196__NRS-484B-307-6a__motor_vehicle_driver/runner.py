"""Partition 04 exact native capability episode; no legal or physical verdict."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from scenario import lane_path, other_path, static_check

ROOT=Path(__file__).resolve().parent


def read_config():
    return json.loads((ROOT/'config.json').read_text())


def check():
    cfg=read_config()
    case=cfg['case']
    assert case['case_id']==cfg['selected_case_id'] and case['target_type']!='baseline'
    assert cfg['actor']=='motor_vehicle_driver'
    assert cfg['mode'] in ('following','absolute_speed','posted_speed','yellow_red','inoperative_signal')
    assert len(cfg['cameras'])==4
    assert (cfg['cameras'][0]['width'],cfg['cameras'][0]['height'])==(1920,1080)
    assert all((c['width'],c['height'])==(1280,720) for c in cfg['cameras'][1:])
    required={o['name'] for o in cfg['observations'] if o.get('mandatory',True)}
    assert required <= {c['name'] for c in case['recording_description']['channels']}
    map_result=static_check(cfg,(ROOT/'scene.xodr').read_text())
    assert cfg['max_ticks']==cfg['duration_s']*20
    assert all(cfg['controller'][key]>0 for key in ('speed_kp','brake_kp','steer_kp','gap_kp'))
    if cfg['mode']=='following':
        assert case['variable_assignments']['commanded_following_gap']['value'] in (15,30,45)
        assert len(other_path(cfg))>100
    elif cfg['mode'] in ('absolute_speed','posted_speed'):
        assert 0<case['variable_assignments']['commanded_approach_speed']['value']<40
    elif cfg['mode']=='yellow_red':
        assert isinstance(case['variable_assignments']['obey_red']['value'],bool)
    else:
        assert isinstance(case['variable_assignments']['commanded_halt']['value'],bool)
    print(json.dumps({'case_id':case['case_id'],'offline_check':'passed',
        'map':map_result,'simulator_connected':False}))


def state(actor):
    t=actor.get_transform();v=actor.get_velocity();c=actor.get_control()
    return {'actor_id':actor.id,'type_id':actor.type_id,'position_m':[t.location.x,t.location.y,t.location.z],
        'heading_deg':t.rotation.yaw,'speed_mps':math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z),
        'velocity_mps':[v.x,v.y,v.z],
        'body_vertices_m':[[p.x,p.y,p.z] for p in actor.bounding_box.get_world_vertices(t)],
        'applied_control':{k:getattr(c,k) for k in ('throttle','brake','steer','hand_brake','reverse')}}


def surface_gap(ego,leader):
    return min(v[0] for v in leader['body_vertices_m'])-max(v[0] for v in ego['body_vertices_m'])


def command(carla,actor,path,speed_target,gains):
    s=state(actor);x,y=s['position_m'][:2]
    index=min(range(len(path)),key=lambda i:(path[i][0]-x)**2+(path[i][1]-y)**2)
    target=path[min(index+8,len(path)-1)]
    angle=math.atan2(target[1]-y,target[0]-x)
    error=(angle-math.radians(s['heading_deg'])+math.pi)%(2*math.pi)-math.pi
    speed=s['speed_mps']
    # No integral windup; actual measured speed remains unchanged in evidence.
    throttle=max(0,min(.9,gains['speed_kp']*(speed_target-speed)))
    brake=max(0,min(.8,gains['brake_kp']*(speed-speed_target)))
    steer=max(-.8,min(.8,gains['steer_kp']*error))
    return carla.VehicleControl(throttle=throttle,brake=brake,steer=steer),index


def signal_inventory(world):
    lights=list(world.get_actors().filter('traffic.traffic_light*'))
    return lights,[{'actor_id':a.id,'type_id':a.type_id,'state':str(a.get_state()),
        'position_m':[a.get_location().x,a.get_location().y,a.get_location().z],
        'body_vertices_m':[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]}
        for a in lights]


def image_for_frame(q,frame):
    image=q.get(timeout=30)
    while image.frame<frame:
        image=q.get(timeout=30)
    if image.frame!=frame:raise RuntimeError('Camera/source frame mismatch')
    return image


def capture_frame_identity(mapping, frame, time_s, **extra):
    return mapping.append(frame,time_s,**extra)

def cleanup_action(errors,label,action):
    try: action()
    except Exception as exc: errors.append({'action':label,'error':repr(exc)})

def run(args):
    import carla  # lazy: --check never imports or connects
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    cfg=read_config();case=cfg['case'];kind=cfg['mode']
    out=Path(args.output_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'physical_samples.jsonl').exists():raise ValueError('Retain prior attempt in a fresh directory')
    if not (out/'config.json').exists():(out/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    client=carla.Client(args.host,args.port);client.set_timeout(120)
    if client.get_client_version()!=client.get_server_version():raise RuntimeError('CARLA client/server version mismatch')
    saved_world=snapshot(client)
    previous=client.get_world();prior_settings=previous.get_settings()
    if prior_settings.synchronous_mode:raise RuntimeError('Endpoint already in synchronous mode; exclusive ownership not established')
    if any(a.type_id.startswith(('vehicle.','walker.','sensor.')) for a in previous.get_actors()):
        raise RuntimeError('Endpoint has active dynamic actors; exclusive ownership not established')
    world=None;actors=[];capture=None;encoders=[];streams={};error=None;count=0
    try:
        world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text())
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        path=lane_path(cfg);bp=world.get_blueprint_library().find('vehicle.tesla.model3');bp.set_attribute('role_name','ego')
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=path[0][0],y=path[0][1],z=.5)))
        actors.append(ego);other=None
        if kind in ('following','inoperative_signal'):
            bp2=world.get_blueprint_library().find('vehicle.tesla.model3')
            bp2.set_attribute('role_name','leader' if kind=='following' else 'earlier_stopped_crossing')
            if kind=='following':
                gap=case['variable_assignments']['commanded_following_gap']['value']
                pose=carla.Transform(carla.Location(x=path[0][0]+gap+5,y=-1.75,z=.5))
            else:
                pose=carla.Transform(carla.Location(x=1.75,y=35,z=.5),carla.Rotation(yaw=-90))
            other=world.spawn_actor(bp2,pose);actors.append(other)
        occluders=[]
        if kind=='inoperative_signal':
            library=world.get_blueprint_library()
            props=[bp for pattern in ('static.prop.container*','static.prop.building*','static.prop.*')
                   for bp in library.filter(pattern)]
            if not props:raise RuntimeError('No static prop blueprint for authored blind-corner occlusion')
            prop=props[0]
            for x,y in [(-16,11),(11,-16)]:
                obstacle=world.try_spawn_actor(prop,carla.Transform(carla.Location(x=x,y=y,z=.5)))
                if obstacle is None:raise RuntimeError('Native blind-corner prop spawn failed')
                actors.append(obstacle);occluders.append(obstacle)
        lights,_=signal_inventory(world)
        if kind in ('yellow_red','inoperative_signal') and len(lights)<4:
            raise RuntimeError('OpenDRIVE four-head signal inventory absent in native map')
        camera_queues=[]
        for i,spec in enumerate(cfg['cameras']):
            camera_bp=world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in [('image_size_x',spec['width']),('image_size_y',spec['height']),('sensor_tick',0)]:
                camera_bp.set_attribute(key,str(value))
            pose=carla.Transform(carla.Location(x=spec['x'],y=spec.get('y',0),z=spec['z']),
                carla.Rotation(pitch=spec['pitch'],yaw=spec.get('yaw',0)))
            camera=world.spawn_actor(camera_bp,pose,attach_to=ego);actors.append(camera)
            q=queue.Queue();camera.listen(q.put);camera_queues.append(q)
            log=(out/('view%d.encoder.log'%i)).open('x')
            encoder=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','bgra','-s','%dx%d'%(spec['width'],spec['height']),'-r','20',
                '-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0','-level','1','-threads','2',
                str(out/('view%d.mkv'%i))],
                stdin=subprocess.PIPE,stderr=log)
            encoders.append((encoder,log))
        for _ in range(5):world.tick()
        (out/'native-setup.json').write_text(json.dumps({'map':world.get_map().name,
            'native_road_ids':sorted({a.road_id for edge in world.get_map().get_topology() for a in edge}),
            'signals':signal_inventory(world)[1],
            'native_landmarks':[{'id':str(l.id),'road_id':l.road_id,'s_m':l.s,'type':str(l.type),
                'value':str(l.value)} for l in world.get_map().get_all_landmarks()],
            'occluders':[{'id':a.id,'type_id':a.type_id,'body_vertices_m':
                [[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]} for a in occluders],
            'synthetic_context':cfg['authored_test_context'],'vehicle_blueprints':[a.type_id for a in actors if a.type_id.startswith('vehicle.')]},indent=2)+'\n')
        capture=PipelineCapture(client,ego,out,case['case_id'],required_observations=cfg['required_atoms'])
        (out/'context.json').write_text(json.dumps({'authored_context':cfg['authored_test_context']},indent=2)+'\n')
        (out/'channels').mkdir()
        streams={c['name']:(out/'channels'/(c['name']+'.jsonl')).open('x') for c in case['recording_description']['channels']}
        start=world.get_snapshot().timestamp.elapsed_seconds;halted_samples=0;stop_release=False
        other_halted_samples=0;other_release=False
        with (out/'capture/evidence.jsonl').open() as evidence, (out/'physical_samples.jsonl').open('x') as physical, \
                FrameMap(out/'video_frames.jsonl') as mapping:
            for i in range(cfg['max_ticks']):
                now=i*.05
                if kind=='yellow_red':
                    light_state=carla.TrafficLightState.Green if now<2 else carla.TrafficLightState.Yellow if now<3 else carla.TrafficLightState.Red
                    for light in lights:light.set_state(light_state);light.freeze(True)
                elif kind=='inoperative_signal':
                    for light in lights:light.set_state(carla.TrafficLightState.Off);light.freeze(True)
                ego_before=state(ego);other_before=state(other) if other else None
                target=case['variable_assignments']['commanded_approach_speed']['value']
                if kind=='yellow_red' and case['variable_assignments']['obey_red']['value'] and now>=3 and ego_before['position_m'][0]<-7:
                    target=0 if ego_before['position_m'][0]>cfg['controller']['red_brake_start_x_m'] else min(target,4)
                if kind=='inoperative_signal' and case['variable_assignments']['commanded_halt']['value']:
                    if ego_before['position_m'][0]>cfg['controller']['stop_brake_start_x_m'] and not stop_release:
                        target=0
                        halted_samples=halted_samples+1 if ego_before['speed_mps']<.05 else 0
                        stop_release=halted_samples>=20
                    if stop_release:target=3
                if kind=='following' and other_before:
                    actual_gap=surface_gap(ego_before,other_before)
                    requested=case['variable_assignments']['commanded_following_gap']['value']
                    target=max(0,min(12,target+cfg['controller']['gap_kp']*(actual_gap-requested)))
                ego_cmd,ego_index=command(carla,ego,path,target,cfg['controller']);ego.apply_control(ego_cmd)
                other_index=None
                if other:
                    other_target=8 if kind=='following' else 4
                    if kind=='inoperative_signal' and not other_release and other_before['position_m'][1]<cfg['controller']['other_brake_start_y_m']:
                        other_target=0
                        other_halted_samples=other_halted_samples+1 if other_before['speed_mps']<.05 else 0
                        other_release=other_halted_samples>=20
                    other_cmd,other_index=command(carla,other,other_path(cfg),other_target,cfg['controller'])
                    other.apply_control(other_cmd)
                frame=world.tick();elapsed=world.get_snapshot().timestamp.elapsed_seconds-start
                captured=capture.capture(frame,elapsed)
                original=json.loads(evidence.readline())
                if original['original_frame']!=frame:raise RuntimeError('Original observation/source frame mismatch')
                ego_state=state(ego);other_state=state(other) if other else None
                _,devices=signal_inventory(world)
                sample={'frame':frame,'time_s':elapsed,'ego':ego_state,'other':other_state,
                    'ego_route_index':ego_index,'other_route_index':other_index,'requested_speed_mps':target,
                    'signal_devices':devices,'controller_halt_released':stop_release,
                    'other_stop_released':other_release,
                    'surface_gap_m':surface_gap(ego_state,other_state) if other_state and kind=='following' else None,
                    'native_road_projection':original['world'].get('road_projection')}
                physical.write(json.dumps(sample)+'\n')
                for name,stream in streams.items():
                    if name=='kin.speed':value=ego_state['speed_mps']
                    elif name=='kin.velocity':value=ego_state['velocity_mps']
                    elif name=='kin.position':value=ego_state['position_m']
                    elif name=='rel.surface_gap':value=sample['surface_gap_m']
                    else:value={'frame':frame,'physical':sample,'original_observations':original['original_observations'],
                        'native_world':original['world'],'legal_predicate_resolved':False}
                    stream.write(json.dumps({'time_s':elapsed,'value':value})+'\n')
                source_frames={}
                for j,q in enumerate(camera_queues):
                    image=image_for_frame(q,frame);raw=bytes(image.raw_data)
                    encoders[j][0].stdin.write(raw)
                    rgb=np.frombuffer(raw,dtype=np.uint8).reshape(image.height,image.width,4)[:,:,:3][:,:,::-1].copy()
                    source_frames['view%d'%j]={'width':image.width,'height':image.height,
                        'source_bgra_sha256':hashlib.sha256(raw).hexdigest(),
                        'source_rgb_sha256':hashlib.sha256(rgb.tobytes()).hexdigest()}
                capture_frame_identity(mapping,frame,elapsed,source_frames=source_frames)
                count+=1
        (out/'capability-run.json').write_text(json.dumps({'case_id':case['case_id'],'frames':count,
            'expected_frames':cfg['max_ticks'],'native_actors':len(actors),'physical_acceptance':False,
            'remaining':['measured target, physical visibility and complete capture audits']},indent=2)+'\n')
    except BaseException as exc:
        error=repr(exc)
        (out/'capability-error.json').write_text(json.dumps({'case_id':case['case_id'],'error':error,
            'frames':count,'partial_evidence_retained':True},indent=2)+'\n')
        raise
    finally:
        cleanup_errors=[]
        for name,stream in streams.items():cleanup_action(cleanup_errors,'channel_close:'+name,stream.close)
        if capture:cleanup_action(cleanup_errors,'capture_close',lambda:capture.close(confirmed=error is None and count==cfg['max_ticks']))
        for i,(encoder,log) in enumerate(encoders):
            cleanup_action(cleanup_errors,'encoder_stdin_close:'+str(i),encoder.stdin.close)
            cleanup_action(cleanup_errors,'encoder_wait:'+str(i),lambda encoder=encoder:encoder.wait(timeout=180))
            cleanup_action(cleanup_errors,'encoder_log_close:'+str(i),log.close)
        for actor in reversed(actors):cleanup_action(cleanup_errors,'actor_destroy:'+str(actor.id),actor.destroy)
        receipt=[]
        cleanup_action(cleanup_errors,'world_restore',lambda:receipt.append(restore(client,saved_world)))
        (out/'restoration-receipt.json').write_text(json.dumps({'world':receipt[0] if receipt else None,
            'cleanup_errors':cleanup_errors},indent=2)+'\n')
        if cleanup_errors:raise RuntimeError('Owned cleanup or world restoration failed: '+json.dumps(cleanup_errors))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int)
    a=p.parse_args()
    if a.check:check()
    else:
        if not a.output_dir or not a.host or not a.port:p.error('Supply output directory, host and port')
        run(a)
