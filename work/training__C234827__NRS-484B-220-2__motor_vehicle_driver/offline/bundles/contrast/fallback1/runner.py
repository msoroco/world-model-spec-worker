"""Exact rotary bundle check and source-preserving, unaccepted Native capture."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check(bundle):
    bundle=Path(bundle)
    config=json.loads((bundle/'config.json').read_text())
    assignment=json.loads((bundle/'assignment-source.json').read_text())
    plan=json.loads((bundle/'case-plan.json').read_text())
    case=config.get('island_side_request')
    candidate=config.get('candidate_id')
    if (config.get('format')!='c234827-native-request-v1' or
            assignment.get('assignment_id')!=config.get('assignment_id') or
            plan.get('assignment_id')!=config.get('assignment_id') or
            case not in ('reference','contrast') or
            candidate not in ('primary','fallback1','fallback2','fallback3') or
            config.get('case_id')!=config['assignment_id']+'__'+case or
            config['case_id'] not in {row['case_id'] for row in plan['cases']} or
            config.get('status')!='unselected_native_request' or
            config.get('physical_island_verified') is not False or
            config.get('frames')!=240 or config.get('rate_hz')!=20):
        raise ValueError('Exact rotary bundle case differs')
    paths={'assignment_sha256':'assignment-source.json',
           'case_plan_sha256':'case-plan.json','road_sha256':'road.xodr',
           'island_geometry_sha256':'island-geometry.json',
           'tracks_sha256':'requested-tracks.jsonl'}
    if any(config.get(key)!=sha(bundle/name) for key,name in paths.items()):
        raise ValueError('Exact rotary source hash differs')
    road=ET.parse(bundle/'road.xodr').getroot()
    arc=road.find('./road/planView/geometry/arc')
    lanes={int(item.attrib['id']):item.attrib['type'] for item in road.findall('.//lane')}
    island=json.loads((bundle/'island-geometry.json').read_text())
    if (lanes!={0:'none',-1:'driving',-2:'driving'} or
            abs(float(arc.attrib['curvature'])-1/22)>1e-9 or
            island['center_xy_m']!=[0,0] or
            island['requested_island_radius_m']!=15 or
            island['physical_island_verified']):
        raise ValueError('Rotary road or island request differs')
    rows=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows)!=240:raise ValueError('Rotary request row count differs')
    direction=1 if case=='reference' else -1
    start=-math.pi/2 if case=='reference' else math.pi/2
    radius=27.25 if candidate=='fallback2' else 23.75
    lane=-2 if candidate=='fallback2' else -1
    speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
    for i,row in enumerate(rows):
        t=(i+1)/20
        distance=min(12,speed*t) if candidate=='fallback3' else speed*t
        angle=start+direction*distance/radius
        if (row.get('frame')!=i or abs(row.get('time_s',-1)-t)>1e-6 or
                row.get('case')!=case or row.get('candidate_id')!=candidate or
                row.get('lane_id')!=lane or row.get('requested_radius_m')!=radius or
                abs(row.get('ego_x_m',1e9)-radius*math.cos(angle))>1e-5 or
                abs(row.get('ego_y_m',1e9)-radius*math.sin(angle))>1e-5 or
                row.get('ego_speed_mps')!=(0 if candidate=='fallback3' and speed*t>12 else speed)):
            raise ValueError('Rotary requested track differs')
    return {'format':'c234827-copied-runner-cpu-check-v1',
            'case_id':config['case_id'],'candidate_id':candidate,
            'requested_frames':240,'carla_imported':False,
            'physical_island_verified':False,'delivery_ready':False}


def repository():
    here=Path(__file__).resolve().parent
    for parent in (here,*here.parents):
        if (parent/'batch.json').is_file() and (parent/'runtime').is_dir():
            return parent
    override=os.environ.get('SCENARIO_REPO_ROOT')
    if override and (Path(override)/'runtime').is_dir():
        return Path(override).resolve()
    raise ValueError('Pinned runtime repository unavailable')


def write_new(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def pose_record(actor):
    pose=actor.get_transform()
    velocity=actor.get_velocity()
    vertices=actor.bounding_box.get_world_vertices(pose)
    return {'actor_id':actor.id,'blueprint':actor.type_id,
        'center_native_xyz_m':[pose.location.x,pose.location.y,pose.location.z],
        'yaw_deg':pose.rotation.yaw,
        'velocity_native_xyz_mps':[velocity.x,velocity.y,velocity.z],
        'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
        'body_native_xyz_m':[[point.x,point.y,point.z] for point in vertices]}


def execute(bundle,output,host,port):
    check(bundle)
    bundle,output=Path(bundle).resolve(),Path(output).resolve()
    if output.exists():
        raise ValueError('Rotary Native output must be a fresh directory')
    root=repository()
    sys.path.insert(0,str(root/'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0,str(root/'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore

    config=json.loads((bundle/'config.json').read_text())
    requests=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    client=carla.Client(host,int(port))
    client.set_timeout(180)
    saved_world=snapshot(client)
    previous=client.get_world()
    if saved_world['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.','walker.','sensor.'))
            for actor in previous.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    output.mkdir(parents=True)
    owned=[];encoders={};logs={};camera_queues={}
    capture=None;changed=False;observed_frames=0;restored=None;error=None
    try:
        world=client.generate_opendrive_world((bundle/'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50,wall_height=0,additional_width=0,
                smooth_junctions=False,enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings()
        settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05
        settings.substepping=True
        settings.max_substep_delta_time=.01
        settings.max_substeps=10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map()
        first=requests[0]
        start=carla.Location(x=first['ego_x_m'],y=-first['ego_y_m'],z=1)
        waypoint=mapping.get_waypoint(start,project_to_road=False,
            lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id!=first['lane_id']:
            raise RuntimeError('Native rotary lane readback differs from request')
        write_new(output/'native-map-readback.json',{
            'road_sha256':sha(bundle/'road.xodr'),
            'island_geometry_sha256':sha(bundle/'island-geometry.json'),
            'native_map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'center_xy_m':[0,0],'island_radius_m':15,
            'driving_lane_ids':[-2,-1],
            'physical_island_verified':False,
            'traffic_control_verified':False})
        library=world.get_blueprint_library()
        blueprint=library.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name','c234827_ego')
        ego=world.spawn_actor(blueprint,carla.Transform(start,
            carla.Rotation(yaw=-first['ego_heading_deg'])))
        owned.append(ego)
        # Each requested pose is a controlled starting condition for one
        # physics tick. The readback below is never replaced by request data.
        cameras=(('forward',1280,720,carla.Transform(
                     carla.Location(x=1.0,y=0,z=1.4))),
                 ('overview',1280,720,carla.Transform(
                     carla.Location(x=0,y=0,z=60),
                     carla.Rotation(pitch=-90))))
        for name,width,height,transform in cameras:
            bp=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),
                              ('fov',90),('sensor_tick',0)):
                bp.set_attribute(key,str(value))
            sensor=world.spawn_actor(bp,transform,
                attach_to=ego if name=='forward' else None)
            owned.append(sensor)
            camera_queues[name]=queue.Queue()
            logs[name]=(output/(name+'.encoder.log')).open('x')
            encoders[name]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}',
                '-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=logs[name])
            sensor.listen(camera_queues[name].put)
        capture=PipelineCapture(client,ego,output,config['case_id'],
                                visibility=False,required_observations=[])
        start_time=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-ego.jsonl').open('x') as observed, \
             (output/'video_frames.jsonl').open('x') as frame_map:
            for i,request in enumerate(requests):
                ego.set_transform(carla.Transform(carla.Location(
                    x=request['ego_x_m'],y=-request['ego_y_m'],z=1),
                    carla.Rotation(yaw=-request['ego_heading_deg'])))
                heading=math.radians(request['ego_heading_deg'])
                speed=request['ego_speed_mps']
                ego.set_target_velocity(carla.Vector3D(
                    x=speed*math.cos(heading),y=-speed*math.sin(heading),z=0))
                frame=world.tick()
                time_s=world.get_snapshot().timestamp.elapsed_seconds-start_time
                pose=pose_record(ego)
                waypoint=mapping.get_waypoint(ego.get_transform().location,
                    project_to_road=False,lane_type=carla.LaneType.Driving)
                if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id not in (-2,-1):
                    raise RuntimeError('Native rotary driving-lane readback absent')
                row={'frame':i,'native_frame':frame,'time_s':time_s,
                    'source_kind':'original_native','case':config['island_side_request'],
                    'native_lane_id':waypoint.lane_id,'ego':pose,
                    'track_application':'controlled_pose_and_target_velocity',
                    'physical_island_review':'pending',
                    'traffic_control_review':'pending','legal_verdict':None}
                capture.capture(frame,time_s,extra={'c234827_rotary':row})
                observed.write(json.dumps(row,allow_nan=False)+'\n')
                for name,width,height,_ in cameras:
                    image=camera_queues[name].get(timeout=30)
                    while image.frame<frame:
                        image=camera_queues[name].get(timeout=30)
                    if image.frame!=frame:
                        raise RuntimeError('Camera and rotary Native frame join differs')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        height,width,4)[:,:,:3][:,:,::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame':i,'native_frame':frame,
                    'time_s':time_s},allow_nan=False)+'\n')
                observed_frames+=1
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),
               'traceback':traceback.format_exc()}
    finally:
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,process in encoders.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180)!=0:
                    raise RuntimeError('Rotary lossless encoder failed: '+name)
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {'cleanup_error':str(exc)}
        if changed:
            try:restored=restore(client,saved_world)
            except BaseException as exc:error=error or {'restore_error':str(exc)}
        write_new(output/'native-capture-report.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'bundle_config_sha256':sha(bundle/'config.json'),
            'requested_frames':240,'observed_frames':observed_frames,
            'track_application':'controlled_pose_and_target_velocity','restoration':restored,
            'error':error,'accepted':False,'physical_island_reviewed':False,
            'traffic_control_reviewed':False,'legal_outcome_claimed':False})
    if error:
        raise RuntimeError('Rotary Native attempt failed; see native-capture-report.json')
    return {'observed_frames':observed_frames,'report':str(output/'native-capture-report.json')}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true')
    mode.add_argument('--run',action='store_true')
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.run:
        if args.output is None:parser.error('--run requires --output')
        print(json.dumps(execute(args.bundle,args.output,args.host,args.port)))
    else:print(json.dumps(check(args.bundle)))
