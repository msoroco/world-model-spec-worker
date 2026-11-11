"""Unaccepted CARLA capture attempt for exact connected C132497 right-exit requests."""
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import traceback

import check as exact

CAMERA_NAMES=('overview','approach','reference_corner','driver_reference')

def camera_plan(policy):
    height=42 if policy=='elevated_overview' else 35
    return (('overview',1920,1080,85,(22,-18,height),(45,-65),False),
            ('approach',1280,720,90,(10,-35,8),(90,-25),False),
            ('reference_corner',1280,720,90,(37,-5,10),(135,-35),False),
            ('driver_reference',1280,720,90,(1,0,1.5),(0,0),True))

def check_capture(bundle):
    checked=exact.check(bundle)
    cfg=json.loads((Path(bundle)/'config.json').read_text())
    plan=camera_plan(cfg['camera_policy'])
    if (tuple(row[0] for row in plan)!=CAMERA_NAMES or
            [list(row[1:3]) for row in plan]!=[[1920,1080],[1280,720],[1280,720],[1280,720]] or
            checked['phases']!=['circulation','entry','exit']):
        raise ValueError('Four-camera right-exit acquisition plan differs')
    return {'case_id':checked['case_id'],'candidate_id':checked['candidate_id'],
            'camera_names':list(CAMERA_NAMES),'camera_dimensions':[list(row[1:3]) for row in plan],
            'camera_positions_m':[list(row[4]) for row in plan],
            'requested_phases':checked['phases'],'original_native_observed':False}

def spawn_camera_sensors(world,carla,ego,policy,owned):
    """Configure and attach each required Native source camera."""
    library=world.get_blueprint_library()
    sensors={}
    for name,width,height,fov,location,rotation,attached in camera_plan(policy):
        camera_bp=library.find('sensor.camera.rgb')
        for key,value in (('image_size_x',width),('image_size_y',height),
                          ('fov',fov),('sensor_tick',0)):
            camera_bp.set_attribute(key,str(value))
        transform=carla.Transform(carla.Location(x=location[0],
            y=location[1],z=location[2]),
            carla.Rotation(yaw=rotation[0],pitch=rotation[1]))
        sensor=world.spawn_actor(camera_bp,transform,
                                 attach_to=ego if attached else None)
        if sensor is None:
            raise RuntimeError('Native source camera spawn failed: '+name)
        owned.append(sensor)
        sensors[name]=sensor
    return sensors

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def repository():
    for parent in (Path(__file__).resolve().parent,*Path(__file__).resolve().parents):
        if (parent/'batch.json').is_file() and (parent/'runtime').is_dir():return parent
    raise ValueError('Pinned runtime repository unavailable')
def write(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def pose(actor):
    transform=actor.get_transform();velocity=actor.get_velocity()
    body=actor.bounding_box.get_world_vertices(transform)
    return {'actor_id':actor.id,'blueprint':actor.type_id,
        'center_native_xyz_m':[transform.location.x,transform.location.y,transform.location.z],
        'yaw_deg':transform.rotation.yaw,
        'velocity_native_xyz_mps':[velocity.x,velocity.y,velocity.z],
        'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
        'body_native_xyz_m':[[p.x,p.y,p.z] for p in body]}
def control(carla,ego,target,target_speed):
    transform=ego.get_transform();velocity=ego.get_velocity()
    speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    angle=math.atan2(target['ego_y_m']-transform.location.y,
        target['ego_x_m']-transform.location.x)
    error=math.atan2(math.sin(angle-math.radians(transform.rotation.yaw)),
        math.cos(angle-math.radians(transform.rotation.yaw)))
    if target_speed<=0:
        return carla.VehicleControl(steer=0,throttle=0,brake=1)
    return carla.VehicleControl(steer=max(-.75,min(.75,1.6*error)),
        throttle=max(0,min(1,.22+.22*(target_speed-speed))),
        brake=max(0,min(1,.4*(speed-target_speed))))

def prepare_output(bundle,output):
    """Accept a fresh materialized runtime attempt or a fresh separate output."""
    bundle=Path(bundle).resolve();output=Path(output).resolve()
    if output.exists():
        if output!=bundle or any((output/name).exists() for name in (
            'native-map-readback.json','native-raw-actors.jsonl','video_frames.jsonl',
            'native-capture-report.json','overview.mkv','capture')):
            raise ValueError('Native output must be a fresh attempt')
    else:
        output.mkdir(parents=True)
    if output!=bundle:
        with (output/'controller-intention.json').open('xb') as stream:
            stream.write((bundle/'controller-intention.json').read_bytes())
    cfg=json.loads((bundle/'config.json').read_text())
    if sha(output/'controller-intention.json')!=cfg['controller_intention_sha256']:
        raise ValueError('Predeclared controller intention changed before capture')
    return bundle,output

def execute(bundle,output,host,port):
    checked=check_capture(bundle)
    bundle,output=prepare_output(bundle,output)
    root=repository();sys.path.insert(0,str(root/'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0,str(root/'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore
    requests=[json.loads(x) for x in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    cfg=json.loads((bundle/'config.json').read_text())
    client=carla.Client(host,int(port));client.set_timeout(180)
    saved=snapshot(client);old=client.get_world()
    if saved['settings'].synchronous_mode or any(
        actor.type_id.startswith(('vehicle.','walker.','sensor.')) for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned=[];video={};logs={};camera_queues={}
    capture=None;changed=False;frames=0;restored=None;error=None
    try:
        world=client.generate_opendrive_world((bundle/'right-exit-road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,
                wall_height=0,additional_width=0,smooth_junctions=False,
                enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True;settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map();lane_readback={}
        for lane,radius in ((-1,16.75),(-2,20.25)):
            theta=-math.pi/4
            point=carla.Location(x=22+radius*math.cos(theta),
                y=radius*math.sin(theta),z=1)
            waypoint=mapping.get_waypoint(point,project_to_road=False,
                lane_type=carla.LaneType.Driving)
            lane_readback[str(lane)]=None if waypoint is None else {
                'road_id':waypoint.road_id,'lane_id':waypoint.lane_id}
            if waypoint is None or waypoint.road_id!=21 or waypoint.lane_id!=lane:
                raise RuntimeError('Generated Native right/other arc lanes differ')
        loop_lane_readback={}
        for lane,radius in ((-1,16.75),(-2,20.25)):
            theta=math.pi/4
            point=carla.Location(x=22+radius*math.cos(theta),
                y=radius*math.sin(theta),z=1)
            waypoint=mapping.get_waypoint(point,project_to_road=False,
                lane_type=carla.LaneType.Driving)
            loop_lane_readback[str(lane)]=None if waypoint is None else {
                'road_id':waypoint.road_id,'lane_id':waypoint.lane_id}
            if waypoint is None or waypoint.road_id!=23 or waypoint.lane_id!=lane:
                raise RuntimeError('Generated Native closed-loop lane readback differs')
        phase_readback={}
        for phase in ('entry','circulation','exit'):
            matching=[row for row in requests if row['phase']==phase]
            if not matching:continue
            sample=matching[len(matching)//2]
            waypoint=mapping.get_waypoint(carla.Location(x=sample['ego_x_m'],
                y=sample['ego_y_m'],z=1),project_to_road=False,
                lane_type=carla.LaneType.Driving)
            phase_readback[phase]=None if waypoint is None else {
                'road_id':waypoint.road_id,'lane_id':waypoint.lane_id}
            if waypoint is None or waypoint.road_id!=sample['road_id'] or waypoint.lane_id!=sample['lane_id']:
                raise RuntimeError('Generated Native requested phase lane differs')
        bp=world.get_blueprint_library().find('vehicle.tesla.model3')
        bp.set_attribute('role_name','c132497_ego')
        first=requests[0]
        ego=world.try_spawn_actor(bp,carla.Transform(carla.Location(
            x=first['ego_x_m'],y=first['ego_y_m'],z=1.5),
            carla.Rotation(yaw=first['ego_heading_deg'])))
        if ego is None:raise RuntimeError('C132497 ego spawn failed')
        owned.append(ego)
        for _ in range(20):world.tick()
        write(output/'native-map-readback.json',{
            'road_sha256':sha(bundle/'right-exit-road.xodr'),
            'native_map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'arc_lane_readback':lane_readback,'loop_lane_readback':loop_lane_readback,
            'phase_lane_readback':phase_readback,
            'ego_actor_id':ego.id,'physical_roundabout_verified':False,
            'lane_allocation_verified':False,'actual_right_exit_verified':False,
            'legal_verdict':None})
        cameras=camera_plan(cfg['camera_policy'])
        sensors=spawn_camera_sensors(world,carla,ego,cfg['camera_policy'],owned)
        for name,width,height,fov,location,rotation,attached in cameras:
            camera_queues[name]=queue.Queue()
            logs[name]=(output/(name+'.encoder.log')).open('x')
            video[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner',
                '-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24',
                '-s',f'{width}x{height}','-r','20','-i','pipe:0','-an',
                '-c:v','ffv1','-level','1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=logs[name])
            sensors[name].listen(camera_queues[name].put)
        capture=PipelineCapture(client,ego,output,cfg['case_id'],
            visibility=False,required_observations=[])
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-actors.jsonl').open('x') as observed, \
             (output/'video_frames.jsonl').open('x') as frame_map:
            for i,request in enumerate(requests):
                target=requests[min(239,i+12)]
                ego.apply_control(control(carla,ego,target,request['ego_speed_mps']))
                frame=world.tick()
                time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                transform=ego.get_transform()
                waypoint=mapping.get_waypoint(transform.location,project_to_road=False,
                    lane_type=carla.LaneType.Driving)
                row={'frame':i,'native_frame':frame,'time_s':time_s,
                    'source_kind':'original_native','requested_phase':request['phase'],
                    'requested_road_id':request['road_id'],
                    'requested_lane_id':request['lane_id'],
                    'observed_road_id':None if waypoint is None else waypoint.road_id,
                    'observed_lane_id':None if waypoint is None else waypoint.lane_id,
                    'ego':pose(ego),'physical_roundabout_verified':False,
                    'actual_right_exit_verified':False,'legal_verdict':None}
                capture.capture(frame,time_s,extra={'c132497_right_exit':row})
                observed.write(json.dumps(row,allow_nan=False)+'\n')
                for name,width,height,_,_,_,_ in cameras:
                    image=camera_queues[name].get(timeout=30)
                    while image.frame<frame:image=camera_queues[name].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Camera/Native frame join differs')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        height,width,4)[:,:,:3][:,:,::-1]
                    video[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame':i,'native_frame':frame,
                    'time_s':time_s},allow_nan=False)+'\n')
                frames+=1
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),
            'traceback':traceback.format_exc()}
    finally:
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,process in video.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180)!=0:raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {'cleanup_error':str(exc)}
        if changed:
            try:restored=restore(client,saved)
            except BaseException as exc:error=error or {'restore_error':str(exc)}
        write(output/'native-capture-report.json',{
            'case_id':checked['case_id'],'candidate_id':checked['candidate_id'],
            'config_sha256':sha(bundle/'config.json'),
            'controller_intention_sha256':sha(output/'controller-intention.json'),
            'requested_frames':240,'observed_frames':frames,
            'camera_names':list(CAMERA_NAMES),
            'camera_dimensions':[list(row[1:3]) for row in cameras],
            'restoration':restored,'error':error,'accepted':False,
            'physical_roundabout_verified':False,'lane_allocation_verified':False,
            'actual_right_exit_verified':False,'legal_verdict':None,
            'delivery_ready':False})
    if error:raise RuntimeError('Native attempt failed; see native-capture-report.json')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,default=Path('.'))
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port',type=int)
    args=parser.parse_args()
    if args.check:
        print(json.dumps(check_capture(args.bundle)))
    else:
        if args.output_dir is None or args.host is None or args.port is None:
            parser.error('Original capture needs output-dir, host and port')
        execute(args.bundle,args.output_dir,args.host,args.port)
