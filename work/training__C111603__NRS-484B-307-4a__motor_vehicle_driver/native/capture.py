"""Acquire original governed-signal, participant and four-camera sources.

Native Green readback is retained as raw device evidence. Only an independent
review of original device pixels can establish a green turn arrow alone.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess

from build_config import CAMERAS
from controller import Observation, request
from survey import load

COUNT = 600
RATE = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')


def pose(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    return {
        'actor_id': actor.id, 'type_id': actor.type_id,
        'x_m': transform.location.x, 'y_m': transform.location.y,
        'z_m': transform.location.z, 'yaw_deg': transform.rotation.yaw,
        'speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
        'body_vertices_native_m': [[p.x, p.y, p.z] for p in
                                   actor.bounding_box.get_world_vertices(transform)],
    }


def inside(xy, bounds):
    return bounds[0] <= xy[0] <= bounds[1] and bounds[2] <= xy[1] <= bounds[3]


def xy_of(actor):
    location = actor.get_transform().location
    return (location.x, location.y)


def spawn_at(world, carla, blueprint, spec):
    if not isinstance(spec, list) or len(spec) != 4:
        raise ValueError('Original surveyed actor pose must be x,y,z,yaw')
    actor = world.try_spawn_actor(blueprint, carla.Transform(
        carla.Location(x=spec[0], y=spec[1], z=spec[2]),
        carla.Rotation(yaw=spec[3])))
    if actor is None:
        raise RuntimeError('Original surveyed actor spawn failed')
    return actor


def follow_route(carla, actor, waypoints, target_speed):
    here = xy_of(actor)
    goal = waypoints[-1]
    for point in waypoints[1:]:
        if math.hypot(point[0]-here[0], point[1]-here[1]) > 2.5:
            goal = point
            break
    desired = math.atan2(goal[1]-here[1], goal[0]-here[0])
    observed = pose(actor)
    error = math.atan2(math.sin(desired-math.radians(observed['yaw_deg'])),
                       math.cos(desired-math.radians(observed['yaw_deg'])))
    delta = target_speed-observed['speed_mps']
    return carla.VehicleControl(
        steer=max(-0.75,min(0.75,1.6*error)),
        throttle=max(0,min(0.7,0.2+0.2*delta)) if target_speed else 0,
        brake=max(0,min(0.8,-0.4*delta)) if target_speed else 0.8)


def locate_head(world, opendrive_id):
    found = []
    for actor in world.get_actors():
        if not str(getattr(actor,'type_id','')).startswith('traffic.traffic_light'):
            continue
        read = getattr(actor,'get_opendrive_id',None)
        if read is not None and str(read()) == str(opendrive_id):
            found.append(actor)
    if len(found) != 1:
        raise ValueError('One original surveyed Native governing-head identity required')
    return found[0]


def derive_channels(output):
    """Project retained Native rows; preserve unresolved legal/source judgments."""
    native=[json.loads(line) for line in (output/'native.jsonl').read_text().splitlines()]
    frames=[json.loads(line) for line in (output/'video_frames.jsonl').read_text().splitlines()]
    context=json.loads((output/'intersection-context.json').read_text())
    if len(native)!=COUNT or len(frames)!=COUNT:
        raise ValueError('Full original Native and four-camera source join required')
    channels=output/'channels';channels.mkdir(exist_ok=False)
    terms={
        'signal_native_and_pixels':lambda row,index:{'signal':row['signal'],'camera_map':frames[index]},
        'participant_native_and_video':lambda row,index:{'actors':row['actors'],'camera_map':frames[index]},
        'dev.traffic_signal':lambda row,index:{'native_signal':row['signal'],
                                                'arrow_pixels_reviewed':False},
        'dev.governs':lambda row,index:{'native_signal':row['signal'],
                                       'arrow_facing_source':context['arrow_facing_source'],
                                       'governance_reviewed':False},
        'drv.turning':lambda row,index:{'ego':row['actors']['ego'],
                                       'requested_phase':row['requested_phase']},
        'kin.heading':lambda row,index:{'ego_yaw_deg':row['actors']['ego']['yaw_deg']},
        'drv.entering_intersection':lambda row,index:{'ego_body':row['actors']['ego']['body_vertices_native_m'],
                                                     'bounds':context['intersection_bounds_m']},
        'ru.pedestrian':lambda row,index:{'pedestrian':row['actors']['pedestrian'],
                                         'lawfulness_reviewed':False},
        'st.crosswalk':lambda row,index:{'bounds':context['adjacent_crosswalk_bounds_m'],
                                        'pedestrian':row['actors']['pedestrian']},
        'drv.in_intersection':lambda row,index:{'other_traffic':row['actors']['other_traffic'],
                                               'bounds':context['intersection_bounds_m'],
                                               'lawfulness_reviewed':False},
        'drv.yields_to':lambda row,index:{'ego':row['actors']['ego'],
                                         'pedestrian':row['actors']['pedestrian'],
                                         'other_traffic':row['actors']['other_traffic'],
                                         'yield_causation_reviewed':False},
    }
    result=[]
    for name,method in terms.items():
        path=channels/(name+'.jsonl')
        path.write_text(''.join(json.dumps({'native_frame':row['native_frame'],
            'time_s':row['time_s'],'value':method(row,index)},allow_nan=False)+'\n'
            for index,row in enumerate(native)))
        result.append({'name':name,'unit':'structured',
                       'reference':str(path.relative_to(output))})
    return result


def execute(config, output, host, port, survey_path=None):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture, write_result
    from worker_exchange.world_restore import snapshot, restore

    case_id = config['selected_case_id']
    suffix = case_id.rsplit('__',1)[-1]
    survey_source = Path(survey_path or os.environ.get('SCENARIO_CONTEXT_SURVEY',''))
    survey = load(survey_source, case_id)
    output = Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file() or any(
            (output/name).exists() for name in ('native.jsonl','video_frames.jsonl','result.json')):
        raise ValueError('Fresh materialized original attempt required')
    client = carla.Client(host,int(port))
    client.set_timeout(180)
    world = client.get_world()
    if world.get_map().name != survey['map_name']:
        raise ValueError('Original surveyed Native map differs')
    head = locate_head(world,survey['arrow_opendrive_id'])
    prior = snapshot(client)
    owned=[]; encoders={}; logs={}; cameras={}; recorder=None
    errors=[]; observed_frames=0; restoration=None
    try:
        settings=world.get_settings()
        settings.synchronous_mode=True
        settings.fixed_delta_seconds=1/RATE
        settings.substepping=True
        settings.max_substep_delta_time=0.01
        settings.max_substeps=10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        vehicle_bp=world.get_blueprint_library().find('vehicle.tesla.model3')
        walker_bp=world.get_blueprint_library().filter('walker.pedestrian.*')[0]
        ego=spawn_at(world,carla,vehicle_bp,survey['ego_spawn_xyz_yaw'])
        other=spawn_at(world,carla,vehicle_bp,survey['other_traffic_spawn_xyz_yaw'])
        pedestrian=spawn_at(world,carla,walker_bp,survey['pedestrian_spawn_xyz_yaw'])
        owned.extend((ego,other,pedestrian))
        for name,width,height,fov in CAMERAS:
            camera_bp=world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),
                              ('fov',fov),('sensor_tick',0)):
                camera_bp.set_attribute(key,str(value))
            if name in ('approach','driver_reference'):
                location=carla.Location(x=1.0 if name=='approach' else 0.2,z=1.6)
                camera=world.spawn_actor(camera_bp,carla.Transform(location),attach_to=ego)
            else:
                spec=survey['camera_poses'][name]
                location=carla.Location(x=spec['xyz_m'][0],y=spec['xyz_m'][1],z=spec['xyz_m'][2])
                angles=spec['pitch_yaw_roll_deg']
                camera=world.spawn_actor(camera_bp,carla.Transform(location,
                    carla.Rotation(pitch=angles[0],yaw=angles[1],roll=angles[2])))
            owned.append(camera)
            frames=queue.Queue();camera.listen(frames.put);cameras[name]=frames
            log=(output/(name+'.encoder.log')).open('x');logs[name]=log
            encoders[name]=subprocess.Popen(
                ['ffmpeg','-nostdin','-v','error','-n','-f','rawvideo',
                 '-pixel_format','bgra','-video_size',f'{width}x{height}',
                 '-framerate',str(RATE),'-i','pipe:0','-frames:v',str(COUNT),
                 '-c:v','ffv1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=log)
        (output/'context-survey.json').write_bytes(survey_source.read_bytes())
        write_new(output/'intersection-context.json',{
            'source_kind':'original_native_context_survey', 'case_id':case_id,
            'survey_sha256':sha(output/'context-survey.json'),
            'map_name':world.get_map().name,
            'map_sha256':hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest(),
            'arrow_opendrive_id':str(survey['arrow_opendrive_id']),
            'arrow_actor_id':head.id,'arrow_direction':survey['arrow_direction'],
            'arrow_facing_source':survey['arrow_facing_source'],
            'arrow_only_pixels_source':survey['arrow_only_pixels_source'],
            'pedestrian_permission_source':survey['pedestrian_permission_source'],
            'other_traffic_permission_source':survey['other_traffic_permission_source'],
            'intersection_bounds_m':survey['intersection_bounds_m'],
            'adjacent_crosswalk_bounds_m':survey['adjacent_crosswalk_bounds_m']})
        recorder=PipelineCapture(client,ego,output,case_id,visibility=False)
        first_time=None
        with ((output/'native.jsonl').open('x') as native,
              (output/'signal_frames.jsonl').open('x') as signal,
              (output/'motion_frames.jsonl').open('x') as motion,
              FrameMap(output/'video_frames.jsonl') as frame_map):
            for i in range(COUNT):
                raw_state=str(head.get_state()).split('.')[-1].lower()
                if raw_state not in ('green','yellow','red','off'):
                    raise ValueError('Original Native signal state unknown')
                ego_xy=xy_of(ego);ped_xy=xy_of(pedestrian);other_xy=xy_of(other)
                obs=Observation(i,not inside(ego_xy,survey['intersection_bounds_m']),
                    inside(ped_xy,survey['adjacent_crosswalk_bounds_m']),
                    inside(other_xy,survey['intersection_bounds_m']),
                    raw_state=='green',pose(ego)['speed_mps'])
                # The controller uses raw Green only as an engineering timing
                # request. Original arrow-alone pixels remain unverified.
                target=request(suffix,obs)
                route=survey[target.route+'_waypoints_xy']
                ego.apply_control(follow_route(carla,ego,route,target.target_speed_mps))
                other.apply_control(follow_route(carla,other,
                    survey.get('other_traffic_waypoints_xy',route),2.5))
                pedestrian.apply_control(carla.WalkerControl(
                    direction=carla.Vector3D(x=0.0,y=1.0,z=0.0),speed=1.0))
                fid=world.tick();snap=world.get_snapshot()
                if snap.frame!=fid:
                    raise RuntimeError('Original Native tick/snapshot mismatch')
                if first_time is None:first_time=snap.timestamp.elapsed_seconds
                t=snap.timestamp.elapsed_seconds-first_time
                if abs(t-i/RATE)>0.005:
                    raise RuntimeError('Original Native 20-Hz time join differs')
                actors={'ego':pose(ego),'pedestrian':pose(pedestrian),'other_traffic':pose(other)}
                camera_frames={}
                for name,_,_,_ in CAMERAS:
                    image=cameras[name].get(timeout=30)
                    if image.frame!=fid:
                        raise RuntimeError('Original four-camera frame join differs')
                    camera_frames[name]=image.frame
                    encoders[name].stdin.write(image.raw_data)
                frame_map.append(fid,t,source_cameras=camera_frames)
                source_row={'source_kind':'original_native','native_frame':fid,'time_s':t,
                    'actors':actors,'signal':{'opendrive_id':str(survey['arrow_opendrive_id']),
                    'native_actor_id':head.id,'raw_state':raw_state,
                    'green_turn_arrow_alone_verified':False},
                    'requested_phase':target.phase,'legal_verdict':None}
                native.write(json.dumps(source_row,allow_nan=False)+'\n')
                signal.write(json.dumps({'native_frame':fid,'time_s':t,
                    'raw_native_state':raw_state,'green_arrow_alone':None,
                    'illuminated':None,'original_pixels_review_pending':True})+'\n')
                motion.write(json.dumps({'native_frame':fid,'time_s':t,
                    'ego_xy_m':ego_xy,'pedestrian_xy_m':ped_xy,
                    'other_traffic_xy_m':other_xy,'ego_speed_mps':actors['ego']['speed_mps'],
                    'ego_heading_xy':[math.cos(math.radians(actors['ego']['yaw_deg'])),
                                      math.sin(math.radians(actors['ego']['yaw_deg']))]})+'\n')
                recorder.capture(fid,t,extra={'green_arrow_source':source_row})
                observed_frames+=1
        for process in encoders.values():
            process.stdin.close()
            if process.wait(timeout=180):
                raise RuntimeError('Original four-camera encoder failed')
        recorder.close(confirmed=True);recorder=None
        write_result(output,{'measured_values':{'original_frames':COUNT,
            'governing_arrow_pixels_verified':False,'participant_lawfulness_verified':False,
            'yield_causation_verified':False},
            'target_checks':[{'target':'source_observed_governed_arrow_and_priority',
                'requested':suffix,'measured':None,'method':'independent source review pending',
                'tolerance':None,'matched':None,'physical_cause_confirmed':False,
                'cause_evidence':'original pixels and participant authority pending'}],
            'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
            'termination_reason':'source_review_pending',
            'physical_failure_flags':['source_review_pending'],
            'trace_reference':'native.jsonl',
            'video_references':[name+'.mkv' for name,_,_,_ in CAMERAS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':config['recording_description'],
            'recording_evidence':derive_channels(output),
            'realized_observables':{'original_frames':COUNT}})
    except BaseException as error:
        errors.append(type(error).__name__+': '+str(error))
        raise
    finally:
        if recorder is not None:recorder.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:process.stdin.close()
                process.kill();process.wait()
        for log in logs.values():log.close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as error:
                errors.append('actor cleanup: '+str(error))
        try:restoration=restore(client,prior)
        except BaseException as error:errors.append('world restore: '+str(error))
        write_new(output/'native-acquisition-report.json',{
            'case_id':case_id,'observed_frames':observed_frames,
            'encoders_closed':all(p.poll() is not None for p in encoders.values()),
            'restoration':restoration,'errors':errors,
            'physical_acceptance_claimed':False,'legal_verdict':None})
        if not errors and observed_frames==COUNT and restoration is not None:
            seal_capture(output,frames=COUNT,restoration=restoration,errors=[],
                encoder_exit_codes={name:p.returncode for name,p in encoders.items()},
                context={'case_id':case_id,'source_review_pending':True})
