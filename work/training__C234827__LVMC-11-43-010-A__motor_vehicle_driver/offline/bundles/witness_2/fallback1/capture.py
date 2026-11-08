"""Source-preserving CARLA attempt for the authored rotary direction requests."""
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import traceback

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def repository():
    for parent in (Path(__file__).resolve().parent,*Path(__file__).resolve().parents):
        if (parent/'batch.json').is_file() and (parent/'runtime').is_dir():return parent
    raise ValueError('Pinned runtime repository unavailable')

def write_new(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')

def pose(actor):
    transform=actor.get_transform();velocity=actor.get_velocity()
    vertices=actor.bounding_box.get_world_vertices(transform)
    return {'actor_id':actor.id,'blueprint':actor.type_id,
            'center_native_xyz_m':[transform.location.x,transform.location.y,transform.location.z],
            'yaw_deg':transform.rotation.yaw,
            'velocity_native_xyz_mps':[velocity.x,velocity.y,velocity.z],
            'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
            'body_native_xyz_m':[[point.x,point.y,point.z] for point in vertices]}

def steering(carla,ego,target,requested_speed):
    transform=ego.get_transform();velocity=ego.get_velocity()
    speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    angle=math.atan2(target['ego_y_m']-transform.location.y,
                     target['ego_x_m']-transform.location.x)
    error=math.atan2(math.sin(angle-math.radians(transform.rotation.yaw)),
                     math.cos(angle-math.radians(transform.rotation.yaw)))
    return carla.VehicleControl(
        steer=max(-.75,min(.75,1.6*error)),
        throttle=max(0,min(1,.22+.22*(requested_speed-speed))),
        brake=max(0,min(1,.4*(speed-requested_speed))))

def execute(bundle,output,host,port,checked):
    bundle=Path(bundle).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Native output must be a fresh directory')
    output.mkdir(parents=True)
    root=repository()
    sys.path.insert(0,str(root/'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0,str(root/'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore
    requests=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    config=json.loads((bundle/'config.json').read_text())
    client=carla.Client(host,int(port));client.set_timeout(180)
    saved=snapshot(client);old=client.get_world()
    if saved['settings'].synchronous_mode or any(
        actor.type_id.startswith(('vehicle.','walker.','sensor.')) for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned=[];video={};logs={};camera_queues={}
    capture=None;changed=False;frames=0;restored=None;error=None
    try:
        world=client.generate_opendrive_world((bundle/'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,
                wall_height=0,additional_width=0,smooth_junctions=False,
                enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map()
        native_lanes={}
        for lane_id,radius in ((-1,23.75),(-2,27.25)):
            point=carla.Location(x=radius/math.sqrt(2),y=-radius/math.sqrt(2),z=1)
            waypoint=mapping.get_waypoint(point,project_to_road=False,
                                          lane_type=carla.LaneType.Driving)
            native_lanes[str(lane_id)]=None if waypoint is None else {
                'road_id':waypoint.road_id,'lane_id':waypoint.lane_id}
            if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id!=lane_id:
                raise RuntimeError('Generated Native rotary lane readback differs')
        first=requests[0];library=world.get_blueprint_library()
        bp=library.find('vehicle.tesla.model3');bp.set_attribute('role_name','c234827_ego')
        ego=world.try_spawn_actor(bp,carla.Transform(
            carla.Location(x=first['ego_x_m'],y=first['ego_y_m'],z=1.5),
            carla.Rotation(yaw=first['ego_heading_deg'])))
        if ego is None:raise RuntimeError('C234827 ego spawn failed')
        owned.append(ego)
        for _ in range(20):world.tick()
        write_new(output/'native-map-readback.json',{
            'road_sha256':sha(bundle/'road.xodr'),
            'island_geometry_sha256':sha(bundle/'island-geometry.json'),
            'native_map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'arc_lane_readback':native_lanes,'ego_actor_id':ego.id,
            'physical_roundabout_verified':False,'traffic_control_verified':False,
            'legal_verdict':None})
        cameras=(('overview',1280,720,85,(0,0,40)),
                 ('forward',1280,720,90,(0,0,0)))
        for name,width,height,fov,location in cameras:
            camera_bp=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),
                              ('fov',fov),('sensor_tick',0)):
                camera_bp.set_attribute(key,str(value))
            transform=(carla.Transform(carla.Location(x=location[0],y=location[1],z=location[2]),
                                       carla.Rotation(pitch=-90)) if name=='overview'
                       else carla.Transform(carla.Location(x=1,y=0,z=1.5)))
            sensor=world.spawn_actor(camera_bp,transform,attach_to=None if name=='overview' else ego)
            owned.append(sensor);camera_queues[name]=queue.Queue()
            logs[name]=(output/(name+'.encoder.log')).open('x')
            video[name]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}',
                '-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=logs[name])
            sensor.listen(camera_queues[name].put)
        capture=PipelineCapture(client,ego,output,config['case_id'],
                                visibility=False,required_observations=[])
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-actors.jsonl').open('x') as observed, \
             (output/'video_frames.jsonl').open('x') as frame_map:
            for i,request in enumerate(requests):
                target=requests[min(239,i+12)]
                ego.apply_control(steering(carla,ego,target,request['ego_speed_mps']))
                frame=world.tick()
                time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                transform=ego.get_transform()
                waypoint=mapping.get_waypoint(transform.location,project_to_road=False,
                                              lane_type=carla.LaneType.Driving)
                row={'frame':i,'native_frame':frame,'time_s':time_s,
                     'source_kind':'original_native','witness':config['direction_request'],
                     'candidate_id':config['candidate_id'],
                     'requested_lane_id':request['lane_id'],
                     'observed_road_id':None if waypoint is None else waypoint.road_id,
                     'observed_lane_id':None if waypoint is None else waypoint.lane_id,
                     'ego':pose(ego),'physical_roundabout_verified':False,
                     'traffic_control_verified':False,'legal_verdict':None}
                capture.capture(frame,time_s,extra={'c234827_rotary':row})
                observed.write(json.dumps(row,allow_nan=False)+'\n')
                for name,width,height,_,_ in cameras:
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
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
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
        write_new(output/'native-capture-report.json',{
            'case_id':checked['case_id'],'candidate_id':checked['candidate_id'],
            'bundle_config_sha256':sha(bundle/'config.json'),
            'requested_frames':240,'observed_frames':frames,
            'restoration':restored,'error':error,'accepted':False,
            'physical_roundabout_verified':False,'traffic_control_verified':False,
            'legal_verdict':None,'delivery_ready':False})
    if error:raise RuntimeError('Native attempt failed; see native-capture-report.json')
