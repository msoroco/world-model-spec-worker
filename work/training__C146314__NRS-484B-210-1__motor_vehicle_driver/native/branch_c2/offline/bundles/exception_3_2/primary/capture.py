"""Unaccepted CARLA attempt for the C146314 paragraph (c)(2) private-way request."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

import check


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repository():
    for parent in (Path(__file__).resolve().parent,*Path(__file__).resolve().parents):
        if (parent/'batch.json').is_file() and (parent/'runtime').is_dir():
            return parent
    raise ValueError('Pinned runtime repository unavailable')


def write_new(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def pose(actor):
    transform=actor.get_transform();velocity=actor.get_velocity()
    body=actor.bounding_box.get_world_vertices(transform)
    return {'actor_id':actor.id,'blueprint':actor.type_id,
        'center_native_xyz_m':[transform.location.x,transform.location.y,
                               transform.location.z],
        'yaw_deg':transform.rotation.yaw,
        'velocity_native_xyz_mps':[velocity.x,velocity.y,velocity.z],
        'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
        'body_native_xyz_m':[[p.x,p.y,p.z] for p in body]}


def steer_to(carla,actor,target_x,target_y,target_speed):
    transform=actor.get_transform();velocity=actor.get_velocity()
    speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    if target_speed<=.05:
        return carla.VehicleControl(steer=0,throttle=0,
                                    brake=max(.5,min(1,speed)))
    angle=math.atan2(target_y-transform.location.y,
                     target_x-transform.location.x)
    error=math.atan2(math.sin(angle-math.radians(transform.rotation.yaw)),
                     math.cos(angle-math.radians(transform.rotation.yaw)))
    return carla.VehicleControl(steer=max(-.65,min(.65,1.4*error)),
        throttle=max(0,min(1,.2+.24*(target_speed-speed))),
        brake=max(0,min(1,.35*(speed-target_speed))))


def execute(bundle,output,host,port):
    bundle=Path(bundle).resolve();output=Path(output).resolve()
    checked=check.check(bundle)
    cfg=json.loads((bundle/'config.json').read_text())
    requests=[json.loads(x) for x in
              (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    root=repository()
    sys.path.insert(0,str(root/'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0,str(root/'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore

    client=carla.Client(host,int(port));client.set_timeout(180)
    old=client.get_world();saved=snapshot(client)
    if old.get_settings().synchronous_mode or any(
        actor.type_id.startswith(('vehicle.','walker.','sensor.'))
        for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    output.mkdir(parents=True,exist_ok=True)
    if any((output/name).exists() for name in
           ('native-raw-actors.jsonl','video_frames.jsonl',
            'native-capture-report.json')):
        raise ValueError('Retain prior C146314 attempt; choose fresh output')
    owned=[];videos={};logs={};camera_queues={}
    pipeline=None;changed=False;frames=0;restored=None;error=None
    lanes_verified=False;private_way_verified=False
    try:
        world=client.generate_opendrive_world(
            (bundle/'unmarked-pass.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50,wall_height=0,additional_width=0,
                smooth_junctions=False,enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map()
        lanes={}
        for lane,y in ((-2,-5.25),(-1,-1.75)):
            wp=mapping.get_waypoint(carla.Location(x=60,y=y,z=1),
                project_to_road=False,lane_type=carla.LaneType.Any)
            lanes[str(lane)]=None if wp is None else {
                'road_id':wp.road_id,'lane_id':wp.lane_id}
            if wp is None or wp.road_id!=212 or wp.lane_id!=lane:
                raise RuntimeError('Generated Native right-pass lanes differ')
        lanes_verified=True
        spur_wp=mapping.get_waypoint(carla.Location(x=48.25,y=-9,z=1),
            project_to_road=False,lane_type=carla.LaneType.Any)
        spur_readback=None if spur_wp is None else {
            'road_id':spur_wp.road_id,'lane_id':spur_wp.lane_id}
        generated=ET.fromstring(mapping.to_opendrive())
        generated_roads={int(road.get('id')) for road in generated.findall('./road')}
        connection=generated.find('./junction/connection[@incomingRoad="212"][@connectingRoad="214"]')
        generated_junction_connection_verified=(214 in generated_roads and connection is not None)
        survey=[]
        for step in range(131):
            x=10+step*.5
            sampled=mapping.get_waypoint(carla.Location(x=x,y=-9,z=1),
                project_to_road=False,lane_type=carla.LaneType.Any)
            survey.append({'x_m':x,'road_id':None if sampled is None else sampled.road_id})
        private_way_verified=(spur_wp is not None and spur_wp.road_id==214 and
            generated_junction_connection_verified and
            any(sample['road_id']==214 for sample in survey))
        if private_way_verified != cfg['private_way_requested']:
            raise RuntimeError('Generated Native private-way spur differs')
        if not cfg['private_way_requested'] and (214 in generated_roads or
                any(sample['road_id']==214 for sample in survey)):
            raise RuntimeError('Unexpected private way in generated full-window survey')
        library=world.get_blueprint_library()
        vehicle_bp=library.find('vehicle.tesla.model3')
        vehicle_bp.set_attribute('role_name','c146314_ego')
        first=requests[0]
        ego=world.try_spawn_actor(vehicle_bp,carla.Transform(
            carla.Location(x=first['ego_x_m'],y=first['ego_y_m'],z=1.5),
            carla.Rotation(yaw=0)))
        if ego is None:raise RuntimeError('C146314 ego spawn failed')
        owned.append(ego)
        lead_bp=library.find('vehicle.tesla.model3')
        lead_bp.set_attribute('role_name','c146314_lead')
        lead=world.try_spawn_actor(lead_bp,carla.Transform(
            carla.Location(x=first['lead_x_m'],y=-1.75,z=1.5),
            carla.Rotation(yaw=0)))
        if lead is None:raise RuntimeError('C146314 lead spawn failed')
        owned.append(lead)
        lead_signal=bool(cfg.get('lead_left_signal_requested',False))
        lead.set_light_state(carla.VehicleLightState.LeftBlinker if lead_signal
                             else carla.VehicleLightState(0))
        for _ in range(20):world.tick()
        write_new(output/'native-map-readback.json',{
            'source_kind':'original_native','road_sha256':sha(bundle/'unmarked-pass.xodr'),
            'native_map_sha256':hashlib.sha256(
                mapping.to_opendrive().encode()).hexdigest(),
            'driving_lane_readback':lanes,'ego_actor_id':ego.id,
            'lead_actor_id':lead.id,
            'authored_shoulder_lane_readback':True,
            'private_way_road_readback':spur_readback,
            'private_way_verified':private_way_verified,
            'generated_junction_connection_verified':generated_junction_connection_verified,
            'private_way_full_window_survey':survey,
            'pavement_condition_verified':False,
            'legal_verdict':None})
        cameras=(('overview',1280,720,85,(60,-18,36)),
                 ('forward',1280,720,90,(1,0,1.5)))
        for name,width,height,fov,location in cameras:
            bp=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),
                              ('fov',fov),('sensor_tick',0)):
                bp.set_attribute(key,str(value))
            transform=(carla.Transform(carla.Location(*location),
                carla.Rotation(pitch=-55)) if name=='overview'
                else carla.Transform(carla.Location(*location)))
            sensor=world.spawn_actor(bp,transform,
                attach_to=None if name=='overview' else ego)
            owned.append(sensor);camera_queues[name]=queue.Queue()
            logs[name]=(output/(name+'.encoder.log')).open('x')
            videos[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner',
                '-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24',
                '-s',f'{width}x{height}','-r','20','-i','pipe:0','-an',
                '-c:v','ffv1','-level','1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=logs[name])
            sensor.listen(camera_queues[name].put)
        pipeline=PipelineCapture(client,ego,output,cfg['case_id'],
            visibility=False,required_observations=[])
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-actors.jsonl').open('x') as observed,\
             (output/'video_frames.jsonl').open('x') as frame_map:
            for i,request in enumerate(requests):
                lookahead=requests[min(239,i+12)]
                ego.apply_control(steer_to(carla,ego,lookahead['ego_x_m'],
                    lookahead['ego_y_m'],
                    0 if cfg['stop_x_m'] is not None and
                         request['ego_x_m']>=cfg['stop_x_m']
                    else cfg['requested_ego_speed_mps']))
                lead.apply_control(steer_to(carla,lead,
                    request['lead_x_m']+3,-1.75,4))
                frame=world.tick()
                time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                ewp=mapping.get_waypoint(ego.get_location(),
                    project_to_road=False,lane_type=carla.LaneType.Any)
                lwp=mapping.get_waypoint(lead.get_location(),
                    project_to_road=False,lane_type=carla.LaneType.Any)
                row={'frame':i,'native_frame':frame,'time_s':time_s,
                    'source_kind':'original_native',
                    'requested_ego_x_m':request['ego_x_m'],
                    'requested_ego_y_m':request['ego_y_m'],
                    'requested_lead_x_m':request['lead_x_m'],
                    'observed_ego_road_id':None if ewp is None else ewp.road_id,
                    'observed_ego_lane_id':None if ewp is None else ewp.lane_id,
                    'observed_lead_road_id':None if lwp is None else lwp.road_id,
                    'observed_lead_lane_id':None if lwp is None else lwp.lane_id,
                    'ego':pose(ego),'lead':pose(lead),
                    'requested_lead_left_signal':lead_signal,
                    'observed_lead_light_state':int(lead.get_light_state()),
                    'observed_lead_left_blinker':bool(
                        lead.get_light_state() & carla.VehicleLightState.LeftBlinker),
                    'authored_shoulder_lane_readback':True,
                    'private_way_road_readback':spur_readback,
                    'private_way_verified':private_way_verified,
                    'actual_private_way_passed_observed':False,
                    'pavement_condition_verified':False,
                    'legal_verdict':None}
                pipeline.capture(frame,time_s,extra={'c146314_paragraph_c2_private_way':row})
                observed.write(json.dumps(row,allow_nan=False)+'\n')
                for name,width,height,_,_ in cameras:
                    image=camera_queues[name].get(timeout=30)
                    while image.frame<frame:
                        image=camera_queues[name].get(timeout=30)
                    if image.frame!=frame:
                        raise RuntimeError('Native camera-frame join differs')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        height,width,4)[:,:,:3][:,:,::-1]
                    videos[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame':i,
                    'native_frame':frame,'time_s':time_s},
                    allow_nan=False)+'\n')
                frames+=1
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),
               'traceback':traceback.format_exc()}
    finally:
        if pipeline is not None:
            try:pipeline.close(confirmed=error is None)
            except BaseException as exc:
                error=error or {'pipeline_close_error':str(exc)}
        for name,process in videos.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180)!=0:
                    raise RuntimeError('Lossless video encoder failed: '+name)
            except BaseException as exc:
                error=error or {'video_encoder_error':str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error=error or {'cleanup_error':str(exc)}
        if changed:
            try:restored=restore(client,saved)
            except BaseException as exc:
                error=error or {'restore_error':str(exc)}
        write_new(output/'native-capture-report.json',{
            'case_id':checked['case_id'],'candidate_id':checked['candidate_id'],
            'config_sha256':sha(bundle/'config.json'),
            'requested_frames':240,'observed_frames':frames,
            'restoration':restored,'error':error,'accepted':False,
            'authored_shoulder_lane_readback':lanes_verified,
            'private_way_verified':private_way_verified,
            'pavement_condition_verified':False,
            'legal_verdict':None,'delivery_ready':False})
    if error:
        raise RuntimeError('C146314 Native attempt failed; see capture report')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--check',action='store_true')
    p.add_argument('--bundle',type=Path,default=Path.cwd())
    p.add_argument('--output-dir',type=Path)
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=2000)
    a=p.parse_args()
    if a.check:
        print(json.dumps(check.check(a.bundle)))
    else:
        if a.output_dir is None:
            p.error('--output-dir is required outside --check')
        execute(a.bundle,a.output_dir,a.host,a.port)
