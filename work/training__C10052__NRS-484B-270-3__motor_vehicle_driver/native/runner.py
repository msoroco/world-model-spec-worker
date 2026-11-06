"""Proposed original Native bicycle-facility stop capture; CPU preflight only.

Requires an exclusively owned supplied CARLA endpoint. This runner never
starts a server, touches campaign state, or decides a legal blocking outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from cameras import camera_plan
from controller import EngineeringKnobs,PathController
from engineering import NAMES,parameters
from geometry import (ALLEY_ENTRANCE_BOUNDS_M,BICYCLE_BOUNDS_M,
                      BICYCLE_LANE_ID,DRIVING_LANE_ID,ROAD_ID,STOP_X_M,STOP_Y_M,
                      check as geometry_check,open_drive,route)

ROOT=Path(__file__).resolve().parent


def write_new(path,value):
    with path.open('x') as output:
        json.dump(value,output,indent=2,allow_nan=False);output.write('\n')


def frame_map_row(index,frame,time_s):
    if type(index) is not int or index<0 or type(frame) is not int or frame<0:
        raise ValueError('Invalid original frame identity')
    if type(time_s) not in (int,float) or not math.isfinite(time_s):
        raise ValueError('Invalid original frame time')
    return {'video_frame':index,'native_frame':frame,'carla_frame':frame,'time_s':time_s}


def check(config):
    geometry=geometry_check();suffix=config['case_suffix'];candidate=config['candidate_id']
    if suffix not in STOP_Y_M or candidate not in NAMES:
        raise ValueError('Unknown exact case or candidate')
    if config['case_id'].rsplit('__',1)[-1]!=suffix or config['cell_id']!='C10052' or config['law_id']!='NRS-484B-270-3':
        raise ValueError('Wrong source-bound case identity')
    if config['duration_s']!=24 or config['rate_hz']!=20:
        raise ValueError('Original capture timing changed')
    engineering=parameters(suffix,candidate)
    route(suffix,engineering['start_x_m'])
    cameras=camera_plan(candidate)
    if [(c['name'],c['width'],c['height']) for c in cameras] != [
        ('overview',1920,1080),('approach',1280,720),
        ('facility',1280,720),('driver_reference',1280,720)]:
        raise ValueError('Four-view source camera contract changed')
    return {'geometry':geometry,'candidate':candidate,'camera_count':len(cameras),
            'native_imported':False,'physical_success_claimed':False}


def body_xy(actor):
    vertices=actor.bounding_box.get_world_vertices(actor.get_transform())
    points=list({(round(v.x,5),round(v.y,5)) for v in vertices})
    if len(points)!=4:raise RuntimeError('Native body lacks four footprint vertices')
    cx=sum(p[0] for p in points)/4;cy=sum(p[1] for p in points)/4
    points.sort(key=lambda p:math.atan2(p[1]-cy,p[0]-cx))
    return [list(p) for p in points]


def map_survey(carla,mapping,native_hash):
    expected={'driving_approach':(-30,-1.5,ROAD_ID,DRIVING_LANE_ID,carla.LaneType.Driving),
              'bicycle_facility':(-12,-4,ROAD_ID,BICYCLE_LANE_ID,carla.LaneType.Biking),
              'alley_entrance':(-1.5,-10,2,-1,carla.LaneType.Driving)}
    identities={}
    for name,(x,y,road_id,lane_id,lane_type) in expected.items():
        waypoint=mapping.get_waypoint(carla.Location(x=x,y=y,z=.2),
            project_to_road=False,lane_type=lane_type)
        if waypoint is None or waypoint.road_id!=road_id or waypoint.lane_id!=lane_id:
            raise RuntimeError('Native road/lane survey failed: '+name)
        identities[name]={'road_id':waypoint.road_id,'lane_id':waypoint.lane_id,
                          'lane_width_m':waypoint.lane_width}
    return {'native_map_sha256':native_hash,'native_lane_survey':identities,
            'road_id':ROAD_ID,'driving_lane_id':DRIVING_LANE_ID,
            'bicycle_lane_id':BICYCLE_LANE_ID,
            'bicycle_facility_native_xy_bounds_m':list(BICYCLE_BOUNDS_M),
            'alley_entrance_native_xy_bounds_m':list(ALLEY_ENTRANCE_BOUNDS_M),
            'native_facility_design_verified':False,
            'boundary_provenance':'authored geometry plus proposed Native lane survey; independent legal facility designation needs saved review'}


def camera_transform(carla,spec):
    x,y,z=spec['xyz_m']
    if spec['attachment']=='world':
        dx,dy,dz=-12-x,-4-y,-z
        yaw=math.degrees(math.atan2(dy,dx))
        pitch=math.degrees(math.atan2(dz,math.hypot(dx,dy)))
    else:yaw=0;pitch=-8
    return carla.Transform(carla.Location(x=x,y=y,z=z),
                           carla.Rotation(pitch=pitch,yaw=yaw))


def execute(config,output,host,port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore
    check(config)
    output=Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file():
        raise ValueError('Use a new materialized exact-case output directory')
    client=carla.Client(host,int(port));client.set_timeout(180)
    saved=snapshot(client);prior_world=client.get_world()
    if saved['settings'].synchronous_mode or [a for a in prior_world.get_actors()
        if a.type_id.startswith(('vehicle.','walker.','sensor.','controller.'))]:
        raise RuntimeError('Requires exclusive idle asynchronous world ownership')
    owned=[];encoders={};encoder_logs={};camera_queues={};channels={}
    capture=None;changed=False;error=None;frames=0;restored=None
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map();native_xml=mapping.to_opendrive()
        native_hash=hashlib.sha256(native_xml.encode()).hexdigest()
        survey=map_survey(carla,mapping,native_hash)
        write_new(output/'road_geometry.json',survey)
        write_new(output/'context.json',{'surveyed_bicycle_facility_and_alley':survey})
        requested_exception_context={
            'source_kind':'synthetic_scene_request',
            'exceptions':{key:False for key in (
                'entering_or_exiting_alley_or_driveway','disabled_vehicle',
                'avoiding_traffic_conflict','official_duties','police_direction',
                'emergency')},
            'note':'requested control context only; absence requires original evidence and independent review'}
        write_new(output/'exception_context.json',{
            **requested_exception_context,
            'requested_exception_context':requested_exception_context})
        suffix=config['case_suffix'];candidate=config['candidate_id']
        engineering=parameters(suffix,candidate)
        start=engineering['start_x_m']
        blueprint=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name','c10052_facility_ego')
        ego=world.spawn_actor(blueprint,carla.Transform(
            carla.Location(x=start,y=-1.5,z=.5),carla.Rotation(yaw=0)))
        owned.append(ego);ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(40):world.tick()
        initial=body_xy(ego)
        if not all(-3<y<0 for x,y in initial):
            raise RuntimeError('Original vehicle body not contained in driving lane at spawn')
        pedestrian_bp=next((bp for bp in world.get_blueprint_library().filter('walker.pedestrian.*')),
                           None)
        if pedestrian_bp is None:raise RuntimeError('Pedestrian control blueprint missing')
        pedestrian_bp.set_attribute('role_name','c10052_pedestrian_control')
        pedestrian=world.spawn_actor(pedestrian_bp,carla.Transform(
            carla.Location(x=8,y=-4,z=.5),carla.Rotation(yaw=0)))
        owned.append(pedestrian)
        wheels=ego.get_physics_control().wheels
        if len(wheels)!=4:raise RuntimeError('Native vehicle wheel geometry unverified')
        wheelbase=(max(w.position.x for w in wheels)-min(w.position.x for w in wheels))/100
        max_steer=max(w.max_steer_angle for w in wheels)
        knobs=EngineeringKnobs(target_speed_mps=engineering['approach_speed_mps'],
            final_brake_mps2=engineering['approach_speed_mps']**2/(2*engineering['braking_start_m']),
            final_margin_m=0)
        native_route=[list(p) for p in route(suffix,start)]
        controller=PathController(native_route,wheelbase,max_steer,knobs)
        write_new(output/'native-construction-context.json',{
            'case_id':config['case_id'],'candidate_id':candidate,
            'native_map_sha256':native_hash,'vehicle_blueprint':ego.type_id,
            'wheelbase_m':wheelbase,'max_steer_deg':max_steer,
            'initial_body_xy_native_m':initial,'controller_knobs':vars(knobs),
            'requested_stop_xy_m':[engineering['stop_x_m'],engineering['stop_y_m']],
            'requested_route_points':len(native_route),
            'pedestrian_control_blueprint':pedestrian.type_id,
            'physical_success_claimed':False})
        for spec in camera_plan(candidate):
            camera_bp=world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in (('image_size_x',spec['width']),('image_size_y',spec['height']),
                              ('fov',spec['fov_deg']),('sensor_tick',0)):
                camera_bp.set_attribute(key,str(value))
            camera=world.spawn_actor(camera_bp,camera_transform(carla,spec),
                attach_to=ego if spec['attachment']=='ego' else None)
            owned.append(camera);camera_queues[spec['name']]=queue.Queue()
            camera.listen(camera_queues[spec['name']].put)
            encoder_logs[spec['name']]=(output/(spec['name']+'.encoder.log')).open('x')
            encoders[spec['name']]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f"{spec['width']}x{spec['height']}",
                '-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(spec['name']+'.mkv'))],stdin=subprocess.PIPE,
                stderr=encoder_logs[spec['name']])
        capture=PipelineCapture(client,ego,output,config['case_id'],visibility=False,
            required_observations=config.get('required_atoms',[]))
        (output/'channels').mkdir()
        for name in config['mandatory_channels']:
            channels[name]=(output/'channels'/(name+'.jsonl')).open('x')
        start_time=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native_samples.jsonl').open('x') as native_file, \
             (output/'body_history.jsonl').open('x') as body_file, \
             (output/'video_frames.jsonl').open('x') as frame_file:
            for index in range(config['duration_s']*config['rate_hz']):
                before=ego.get_transform();velocity=ego.get_velocity()
                speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                command=controller.step(position_xy_m=(before.location.x,before.location.y),
                    yaw_rad=math.radians(before.rotation.yaw),speed_mps=speed,dt_s=.05)
                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],
                    brake=command['brake'],steer=command['steer'],
                    hand_brake=command['hand_brake']))
                frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds-start_time
                pose=ego.get_transform();forward=pose.get_forward_vector();body=body_xy(ego)
                velocity=ego.get_velocity();speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                lane_type=carla.LaneType.Biking if pose.location.y<-3.0 else carla.LaneType.Driving
                lane=mapping.get_waypoint(pose.location,project_to_road=False,
                    lane_type=lane_type)
                if lane is None:raise RuntimeError('Original Native lane identity missing')
                horizontal=math.hypot(forward.x,forward.y)
                if horizontal<.99:raise RuntimeError('Original Native heading invalid')
                sample={'time_s':time_s,'native_frame':frame,
                    'native_center_xy_m':[pose.location.x,pose.location.y],
                    'native_forward_xy':[forward.x/horizontal,forward.y/horizontal],
                    'native_body_xy_m':body,'speed_mps':speed,
                    'native_road_id':lane.road_id,'native_lane_id':lane.lane_id,
                    'controller_request':command}
                capture.capture(frame,time_s,extra={'c10052_native':sample})
                native_file.write(json.dumps(sample,allow_nan=False)+'\n')
                vertices=ego.bounding_box.get_world_vertices(pose)
                body_file.write(json.dumps({'frame':frame,'time_s':time_s,
                    'body_vertices_m':[[v.x,v.y,v.z] for v in vertices]},allow_nan=False)+'\n')
                values={'st.bicycle_lane_or_path':survey,
                    'st.driveway_or_alley_entrance':survey,
                    'rel.occupies':body,'kin.extent':{'body_xy_m':body},
                    'kin.position':sample['native_center_xy_m'],'ego_speed':speed,
                    'drv.standing_or_parked':{'observed_speed_mps':speed,
                        'requested_stop_xy_m':[engineering['stop_x_m'],engineering['stop_y_m']]},
                    'ru.pedestrian':{'native_actor_id':pedestrian.id,
                        'native_xy_m':[pedestrian.get_location().x,pedestrian.get_location().y]},
                    'exception_context':{'source':'exception_context.json',
                        'observed_exception_status':'unresolved'},
                    'native_body_pose_control':sample,
                    'camera_frame_join':frame_map_row(index,frame,time_s)}
                for name,stream in channels.items():
                    stream.write(json.dumps({'time_s':time_s,'value':values[name]},
                                            allow_nan=False)+'\n')
                for spec in camera_plan(candidate):
                    image=camera_queues[spec['name']].get(timeout=30)
                    while image.frame<frame:image=camera_queues[spec['name']].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Original camera/Native frame join failed')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        spec['height'],spec['width'],4)[:,:,:3][:,:,::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                frame_file.write(json.dumps(frame_map_row(index,frame,time_s))+'\n')
                frames+=1
        if frames!=480:raise RuntimeError('Original frame count incomplete')
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        for stream in channels.values():stream.close()
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180)!=0:raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {'owned_actor_cleanup_error':str(exc)}
        if changed:
            try:restored=restore(client,saved)
            except BaseException as exc:error=error or {'world_restore_error':str(exc)}
        write_new(output/'native-capture-report.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'frames':frames,'expected_frames':480,'restoration':restored,
            'error':error,'accepted':False,
            'required_saved_checks':['actual original pixels and pedestrian control',
                'Native bicycle facility and alley designation','stop duration and full-body occupancy',
                'all six exception branches and yield duty','independent legal/physical review']})
    if error:raise RuntimeError('Native attempt failed; see native-capture-report.json: '+str(error))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir');parser.add_argument('--host');parser.add_argument('--port',type=int)
    args=parser.parse_args()
    config=json.loads((ROOT/'config.json').read_text())
    if args.check:print(json.dumps(check(config),allow_nan=False))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Supply materialized output directory, host and port')
        execute(config,args.output_dir,args.host,args.port)


if __name__=='__main__':main()
