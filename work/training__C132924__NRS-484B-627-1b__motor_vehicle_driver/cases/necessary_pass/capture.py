"""Original Native roundabout acquisition; legal judgments remain open."""

import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess

from controller import SourceState, request
from measure import measure

COUNT = 600
RATE = 20
CAMERAS = (('overview', 1920, 1080, 85),
           ('approach', 1280, 720, 90),
           ('reference_corner', 1280, 720, 85),
           ('driver_reference', 1280, 720, 90))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def position(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    return {'actor_id': actor.id, 'x_m': transform.location.x,
            'y_m': transform.location.y, 'z_m': transform.location.z,
            'yaw_deg': transform.rotation.yaw,
            'speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            'body_vertices_native_m': [[p.x, p.y, p.z] for p in
                                       actor.bounding_box.get_world_vertices(transform)]}


def geometry_of(actor, center):
    pose = position(actor)
    angle = math.atan2(pose['y_m'] - center[1], pose['x_m'] - center[0])
    radius = math.hypot(pose['x_m'] - center[0], pose['y_m'] - center[1])
    return pose, radius, angle


def control_to(carla, actor, center, target_radius, target_speed):
    pose, _, angle = geometry_of(actor, center)
    lead = angle + .22
    target_x = center[0] + target_radius * math.cos(lead)
    target_y = center[1] + target_radius * math.sin(lead)
    desired = math.atan2(target_y - pose['y_m'], target_x - pose['x_m'])
    error = math.atan2(math.sin(desired - math.radians(pose['yaw_deg'])),
                       math.cos(desired - math.radians(pose['yaw_deg'])))
    speed_error = target_speed - pose['speed_mps']
    return carla.VehicleControl(steer=max(-.75, min(.75, 1.6 * error)),
                                throttle=max(0, min(.7, .22 + .2 * speed_error)),
                                brake=max(0, min(.8, -.35 * speed_error)))


def survey_for(case_id, explicit=None):
    source = Path(explicit or os.environ.get('SCENARIO_CONTEXT_SURVEY', ''))
    if not source.is_file():
        raise ValueError('Original Native roundabout context survey required')
    survey = json.loads(source.read_text())
    required = ('case_id', 'source_kind', 'map_name', 'roundabout_center_xy_m',
                'outer_right_lane_id', 'inner_left_lane_id',
                'outer_right_lane_radius_m', 'inner_left_lane_radius_m',
                'same_direction_marked_lanes_source', 'lane_marking_source',
                'ego_spawn_xyz_yaw', 'follower_spawn_xyz_yaw',
                'camera_poses', 'roundabout_direction_source')
    if (survey.get('case_id') != case_id or
            survey.get('source_kind') != 'original_native_context_survey' or
            any(not survey.get(key) for key in required) or
            set(survey['camera_poses']) != {'overview', 'reference_corner'}):
        raise ValueError('Original roundabout survey identity or source incomplete')
    if case_id.endswith(('necessary_pass', 'post_pass_linger')) and not survey.get('slower_vehicle_spawn_xyz_yaw'):
        raise ValueError('Original slower-vehicle spawn survey required')
    outer, inner = survey['outer_right_lane_radius_m'], survey['inner_left_lane_radius_m']
    if not (len(outer) == len(inner) == 2 and
            0 < inner[0] < inner[1] <= outer[0] < outer[1]):
        raise ValueError('Original roundabout lane radii invalid')
    return source, survey


def actor_at(world, carla, blueprint, pose):
    if not isinstance(pose, list) or len(pose) != 4:
        raise ValueError('Surveyed actor pose must be x,y,z,yaw')
    actor = world.try_spawn_actor(blueprint, carla.Transform(
        carla.Location(x=pose[0], y=pose[1], z=pose[2]),
        carla.Rotation(yaw=pose[3])))
    if actor is None:
        raise RuntimeError('Surveyed roundabout actor spawn failed')
    return actor


def derive_channels(output):
    native = [json.loads(x) for x in (output/'native.jsonl').read_text().splitlines()]
    frames = [json.loads(x) for x in (output/'video_frames.jsonl').read_text().splitlines()]
    if len(native) != COUNT or len(frames) != COUNT:
        raise ValueError('Full original source and camera join required')
    channels = output/'channels'
    channels.mkdir(exist_ok=False)
    result = []
    for name, records in (
        ('native_lane_body_follower_and_pass', native),
        ('four_camera_video', [r['source_cameras'] for r in frames])):
        path = channels/(name+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s': i/RATE, 'value': row},
                                           allow_nan=False)+'\n' for i,row in enumerate(records)))
        result.append({'name': name, 'unit': 'structured',
                       'reference': str(path.relative_to(output))})
    return result


def execute(config, output, host, port, survey_path=None):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture, write_result
    from worker_exchange.world_restore import snapshot, restore

    case_id = config['selected_case_id']
    suffix = case_id.rsplit('__', 1)[-1]
    survey_source, survey = survey_for(case_id, survey_path)
    output = Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file() or any(
            (output/name).exists() for name in ('native.jsonl', 'video_frames.jsonl', 'result.json')):
        raise ValueError('Original attempt requires fresh materialized bundle')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    world = client.get_world()
    if world.get_map().name != survey['map_name']:
        raise ValueError('Original roundabout survey map differs')
    center = survey['roundabout_center_xy_m']
    prior = snapshot(client)
    owned = []
    encoders = {}
    encoder_logs = {}
    cameras = {}
    recorder = None
    errors = []
    observed_frames = 0
    restoration = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        ego = actor_at(world, carla, blueprint, survey['ego_spawn_xyz_yaw'])
        follower = actor_at(world, carla, blueprint, survey['follower_spawn_xyz_yaw'])
        owned.extend((ego, follower))
        slower = None
        if survey.get('slower_vehicle_spawn_xyz_yaw'):
            slower = actor_at(world, carla, blueprint, survey['slower_vehicle_spawn_xyz_yaw'])
            owned.append(slower)
        lane_readback = {}
        for name, actor in (('ego', ego), ('follower', follower)):
            point = actor.get_transform().location
            waypoint = world.get_map().get_waypoint(point, project_to_road=False,
                                                      lane_type=carla.LaneType.Driving)
            if waypoint is None:
                raise RuntimeError('Original roundabout Native lane readback missing')
            lane_readback[name] = {'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id}
        expected_lane = survey['outer_right_lane_id'] if suffix in ('probe_a', 'necessary_pass', 'post_pass_linger') else survey['inner_left_lane_id']
        if lane_readback['ego']['lane_id'] != expected_lane:
            raise RuntimeError('Original ego surveyed lane readback differs')
        for name,width,height,fov in CAMERAS:
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),('fov',fov),('sensor_tick',0)):
                camera_bp.set_attribute(key,str(value))
            if name in ('approach','driver_reference'):
                pose = carla.Transform(carla.Location(x=1.0 if name=='approach' else .2,z=1.6))
                camera = world.spawn_actor(camera_bp,pose,attach_to=ego)
            else:
                spec = survey['camera_poses'][name]
                pose = carla.Transform(carla.Location(*spec['xyz_m']),carla.Rotation(*spec['pitch_yaw_roll_deg']))
                camera = world.spawn_actor(camera_bp,pose)
            owned.append(camera)
            frames = queue.Queue()
            camera.listen(frames.put)
            cameras[name] = frames
            log = (output/(name+'.encoder.log')).open('x')
            encoder_logs[name] = log
            encoders[name] = subprocess.Popen(
                ['ffmpeg','-nostdin','-v','error','-n','-f','rawvideo','-pixel_format','bgra',
                 '-video_size',f'{width}x{height}','-framerate',str(RATE),'-i','pipe:0',
                 '-frames:v',str(COUNT),'-c:v','ffv1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=log)
        (output/'context-survey.json').write_bytes(survey_source.read_bytes())
        write_new(output/'geometry.json', {
            'source_kind':'original_native','case_id':case_id,
            'survey_sha256':sha(output/'context-survey.json'),
            'map_name':world.get_map().name,
            'map_sha256':hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest(),
            'direction':'counterclockwise','center_xy_m':center,
            'outer_right_lane_radius_m':survey['outer_right_lane_radius_m'],
            'inner_left_lane_radius_m':survey['inner_left_lane_radius_m'],
            'same_direction_marked_lanes_source':survey['same_direction_marked_lanes_source'],
            'lane_marking_source':survey['lane_marking_source'],
            'lane_readback':lane_readback})
        recorder = PipelineCapture(client,ego,output,case_id,visibility=False)
        first_time = None
        seen_slow_ahead = False
        with (output/'native.jsonl').open('x') as native, FrameMap(output/'video_frames.jsonl') as frame_map:
            for i in range(COUNT):
                ego_pose,ego_radius,ego_angle = geometry_of(ego,center)
                follow_pose,_,follow_angle = geometry_of(follower,center)
                follower_gap = ego_radius*((ego_angle-follow_angle)%(2*math.pi))
                slow_pose = None
                if slower is not None:
                    slow_pose,_,slow_angle = geometry_of(slower,center)
                    ahead_arc = ego_radius*((slow_angle-ego_angle)%(2*math.pi))
                    slow_ahead = ahead_arc < math.pi*ego_radius
                    seen_slow_ahead |= slow_ahead
                    cleared = seen_slow_ahead and not slow_ahead
                else:
                    ahead_arc = None
                    cleared = False
                state = SourceState(ego_pose['speed_mps'],ego_radius,follower_gap,
                                    ahead_arc,slow_pose['speed_mps'] if slow_pose else None,
                                    cleared,
                                    sum(survey['outer_right_lane_radius_m'])/2,
                                    sum(survey['inner_left_lane_radius_m'])/2)
                target = request(suffix,state)
                ego.apply_control(control_to(carla,ego,center,target.target_radius_m,target.target_speed_mps))
                follower.apply_control(control_to(carla,follower,center,ego_radius,5.0))
                if slower is not None:
                    slower.apply_control(control_to(carla,slower,center,
                        sum(survey['outer_right_lane_radius_m'])/2,2.0))
                fid = world.tick()
                snap = world.get_snapshot()
                if snap.frame != fid:
                    raise RuntimeError('Native tick/snapshot mismatch')
                if first_time is None:
                    first_time = snap.timestamp.elapsed_seconds
                t = snap.timestamp.elapsed_seconds-first_time
                if abs(t-i/RATE)>.005:
                    raise RuntimeError('Original Native 20-Hz time join differs')
                actor_rows = {'ego':position(ego),'follower':position(follower)}
                if slower is not None:
                    actor_rows['slower_vehicle'] = position(slower)
                camera_frames = {}
                for name,_,_,_ in CAMERAS:
                    image = cameras[name].get(timeout=30)
                    if image.frame != fid:
                        raise RuntimeError('Original four-camera Native frame join differs')
                    camera_frames[name] = image.frame
                    encoders[name].stdin.write(image.raw_data)
                frame_map.append(fid,t,source_cameras=camera_frames)
                row = {'source_kind':'original_native','native_frame':fid,'time_s':t,
                       'actors':actor_rows,
                       'pass_observation':None if slower is None else {
                           'slower_vehicle_ahead':slow_ahead,
                           'slower_vehicle_cleared':cleared,
                           'source_actor_id':slower.id},
                       'requested_phase':target.phase,'legal_verdict':None}
                native.write(json.dumps(row,allow_nan=False)+'\n')
                recorder.capture(fid,t,extra={'roundabout_source':row})
                observed_frames += 1
        for process in encoders.values():
            process.stdin.close()
            if process.wait(timeout=180):
                raise RuntimeError('Original source-camera encoder failed')
        recorder.close(confirmed=True)
        recorder = None
        observed = measure(output/'config.json',output/'native.jsonl',
                           output/'video_frames.jsonl',output/'geometry.json')
        write_new(output/'source-measurement.json',observed)
        write_result(output,{'measured_values':observed,
            'target_checks':[{'target':'source_observed_roundabout_lane_and_pass',
                'requested':suffix,'measured':None,'method':'independent original source review pending',
                'tolerance':None,'matched':None,'physical_cause_confirmed':False,
                'cause_evidence':'original source review pending'}],
            'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
            'termination_reason':'source_review_pending','physical_failure_flags':['source_review_pending'],
            'trace_reference':'native.jsonl','video_references':[name+'.mkv' for name,_,_,_ in CAMERAS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':config['recording_description'],
            'recording_evidence':derive_channels(output),'realized_observables':observed})
    except BaseException as error:
        errors.append(f'{type(error).__name__}: {error}')
        raise
    finally:
        if recorder is not None:
            recorder.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
        for log in encoder_logs.values():
            log.close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as error:
                errors.append('actor cleanup: '+str(error))
        try:
            restoration = restore(client,prior)
        except BaseException as error:
            errors.append('world restore: '+str(error))
        write_new(output/'native-acquisition-report.json',{
            'case_id':case_id,'observed_frames':observed_frames,
            'encoders_closed':all(p.poll() is not None for p in encoders.values()),
            'restoration':restoration,'errors':errors,
            'physical_acceptance_claimed':False,'legal_verdict':None})
        if not errors and observed_frames==COUNT and restoration is not None:
            seal_capture(output,frames=COUNT,restoration=restoration,errors=[],
                         encoder_exit_codes={name:p.returncode for name,p in encoders.items()},
                         context={'case_id':case_id,'source_review_pending':True})
