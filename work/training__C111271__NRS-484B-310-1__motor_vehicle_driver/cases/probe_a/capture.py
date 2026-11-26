"""Original Native flashing-red acquisition; no legal or physical verdict."""

import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess

from controller import State, command
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


def derive_channels(output):
    native = [json.loads(line) for line in (output / 'native.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (output / 'video_frames.jsonl').read_text().splitlines()]
    if len(native) != COUNT or len(frames) != COUNT:
        raise ValueError('Full original source and four-camera join required')
    channels = output / 'channels'
    channels.mkdir(exist_ok=False)
    data = {
        'native_signal_reference_body_and_conflict': [
            {'time_s': row['time_s'], 'value': row} for row in native],
        'four_camera_video': [
            {'time_s': row['time_s'], 'value': row['source_cameras']}
            for row in frames]}
    result = []
    for name, rows in data.items():
        path = channels / (name + '.jsonl')
        path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
        result.append({'name': name, 'unit': 'structured',
                       'reference': str(path.relative_to(output))})
    return result


def survey_for(case_id, survey_path):
    source = Path(survey_path or os.environ.get('SCENARIO_CONTEXT_SURVEY', ''))
    if not source.is_file():
        raise ValueError('Original Native context survey required')
    survey = json.loads(source.read_text())
    required = ('case_id', 'source_kind', 'map_name', 'signal_actor_id',
                'official_device_source', 'signal_head_facing_source',
                'ego_spawn_xyz_m', 'ego_yaw_deg', 'route_origin_xyz_m',
                'route_direction_xy', 'reference_kind', 'reference_s_m',
                'intersection_polygon_xy_m', 'camera_poses',
                'signal_head_forward_xy')
    if survey.get('source_kind') != 'original_native_context_survey' or \
            survey.get('case_id') != case_id or any(not survey.get(key) for key in required):
        raise ValueError('Original survey identity or source fields incomplete')
    direction = survey['route_direction_xy']
    if len(direction) != 2 or abs(math.hypot(*direction) - 1) > .01:
        raise ValueError('Original route direction must be unit length')
    if set(survey['camera_poses']) != {'overview', 'reference_corner'}:
        raise ValueError('Original fixed-camera survey incomplete')
    suffix = case_id.rsplit('__', 1)[-1]
    expected = ('limit_line' if suffix in ('probe_a', 'probe_b') else
                'crosswalk' if suffix.startswith('crosswalk_') else 'intersection')
    if survey['reference_kind'] != expected:
        raise ValueError('Original survey names another stopping-reference branch')
    return source, survey


def projected_front(actor, origin, direction):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    values = [((p.x - origin[0]) * direction[0] +
               (p.y - origin[1]) * direction[1]) for p in vertices]
    return max(values), [[p.x, p.y, p.z] for p in vertices]


def conflict_occupied(world, ego_id, polygon):
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    participants = []
    for actor in world.get_actors().filter('vehicle.*'):
        if actor.id == ego_id:
            continue
        points = actor.bounding_box.get_world_vertices(actor.get_transform())
        if any(min(xs) <= point.x <= max(xs) and min(ys) <= point.y <= max(ys)
               for point in points):
            participants.append(actor.id)
    return bool(participants), participants


def execute(config, output, host, port, survey_path=None):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture, write_result
    from worker_exchange.world_restore import snapshot, restore

    case_id = config['selected_case_id']
    survey_source, survey = survey_for(case_id, survey_path)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file() or any(
            (output / name).exists() for name in
            ('native.jsonl', 'video_frames.jsonl', 'result.json', 'native-acquisition-report.json')):
        raise ValueError('Original attempt requires a fresh materialized bundle')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    world = client.get_world()
    if world.get_map().name != survey['map_name']:
        raise ValueError('Original survey map differs from Native world')
    light = world.get_actor(int(survey['signal_actor_id']))
    if light is None or not light.type_id.startswith('traffic.traffic_light'):
        raise ValueError('Original surveyed traffic signal actor absent')
    forward = light.get_transform().get_forward_vector()
    surveyed_forward = survey['signal_head_forward_xy']
    if (len(surveyed_forward) != 2 or math.hypot(forward.x - surveyed_forward[0],
                                                forward.y - surveyed_forward[1]) > .05):
        raise ValueError('Original signal-head orientation differs from survey')
    prior = snapshot(client)
    prior_light = light.get_state()
    owned = []
    encoders = {}
    encoder_logs = {}
    cameras = {}
    recorder = None
    sealed = False
    errors = []
    native_count = 0
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        bp = world.get_blueprint_library().find('vehicle.tesla.model3')
        bp.set_attribute('role_name', 'c111271_ego')
        xyz = survey['ego_spawn_xyz_m']
        ego = world.try_spawn_actor(bp, carla.Transform(carla.Location(*xyz),
                                  carla.Rotation(yaw=survey['ego_yaw_deg'])))
        if ego is None:
            raise RuntimeError('Original surveyed ego spawn failed')
        owned.append(ego)
        for name, width, height, fov in CAMERAS:
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', fov), ('sensor_tick', 0)):
                camera_bp.set_attribute(key, str(value))
            if name in ('approach', 'driver_reference'):
                pose = carla.Transform(carla.Location(x=1.0 if name == 'approach' else .2,
                                                     z=1.6))
                camera = world.spawn_actor(camera_bp, pose, attach_to=ego)
            else:
                camera_pose = survey['camera_poses'][name]
                pose = carla.Transform(carla.Location(*camera_pose['xyz_m']),
                                       carla.Rotation(*camera_pose['pitch_yaw_roll_deg']))
                camera = world.spawn_actor(camera_bp, pose)
            owned.append(camera)
            source_queue = queue.Queue()
            camera.listen(source_queue.put)
            cameras[name] = source_queue
            log = (output / (name + '.encoder.log')).open('x')
            encoder_logs[name] = log
            encoders[name] = subprocess.Popen(
                ['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'rawvideo',
                 '-pixel_format', 'bgra', '-video_size', f'{width}x{height}',
                 '-framerate', str(RATE), '-i', 'pipe:0', '-frames:v', str(COUNT),
                 '-c:v', 'ffv1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=log)
        (output / 'context-survey.json').write_bytes(survey_source.read_bytes())
        write_new(output / 'geometry.json', {
            'source_kind': 'original_native', 'case_id': case_id,
            'survey_sha256': sha(output / 'context-survey.json'),
            'map_name': world.get_map().name,
            'map_sha256': hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest(),
            'official_device_source': survey['official_device_source'],
            'signal_head_facing_source': survey['signal_head_facing_source'],
            'signal_head_id': str(light.id),
            'limit_line_x_m': survey['reference_s_m'] if survey['reference_kind'] == 'limit_line' else None,
            'crosswalk_near_x_m': survey['reference_s_m'] if survey['reference_kind'] == 'crosswalk' else None,
            'intersection_near_x_m': survey['reference_s_m'],
            'reference_kind': survey['reference_kind'],
            'intersection_polygon_xy_m': survey['intersection_polygon_xy_m']})
        origin = survey['route_origin_xyz_m']
        direction = survey['route_direction_xy']
        control_state = State()
        recorder = PipelineCapture(client, ego, output, case_id, visibility=False)
        initial_time = None
        with (output / 'native.jsonl').open('x') as native, \
             FrameMap(output / 'video_frames.jsonl') as frames:
            for i in range(COUNT):
                light.set_state(carla.TrafficLightState.Red if (i // 10) % 2 == 0
                                else carla.TrafficLightState.Off)
                front, _ = projected_front(ego, origin, direction)
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                occupied, conflict_ids = conflict_occupied(
                    world, ego.id, survey['intersection_polygon_xy_m'])
                control = command(case_id.rsplit('__', 1)[-1], front, speed,
                                  survey['reference_s_m'], occupied, control_state)
                ego.apply_control(carla.VehicleControl(
                    throttle=control['throttle'], brake=control['brake'],
                    hand_brake=control['hand_brake']))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Original Native frame and snapshot differ')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                if abs(time_s - i / RATE) > .005:
                    raise RuntimeError('Original 20-Hz time join differs')
                front, body = projected_front(ego, origin, direction)
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                state = light.get_state()
                lamp = 'red' if state == carla.TrafficLightState.Red else \
                       'off' if state == carla.TrafficLightState.Off else None
                if lamp is None:
                    raise RuntimeError('Original signal phase readback differs')
                occupied, conflict_ids = conflict_occupied(
                    world, ego.id, survey['intersection_polygon_xy_m'])
                camera_frames = {}
                for name, _, _, _ in CAMERAS:
                    image = cameras[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Four-camera Native frame join differs')
                    camera_frames[name] = image.frame
                    encoders[name].stdin.write(image.raw_data)
                frames.append(native_frame, time_s, source_cameras=camera_frames)
                row = {'source_kind': 'original_native', 'native_frame': native_frame,
                       'time_s': time_s, 'front_x_m': front, 'speed_mps': speed,
                       'body_vertices_native_m': body, 'signal_head_id': str(light.id),
                       'signal_lamp_state': lamp, 'signal_faces_ego_observed': True,
                       'signal_head_facing_source': survey['signal_head_facing_source'],
                       'conflict_occupied': occupied, 'conflict_actor_ids': conflict_ids,
                       'requested_control': control, 'legal_verdict': None}
                native.write(json.dumps(row, allow_nan=False) + '\n')
                recorder.capture(native_frame, time_s, extra={'flashing_red_source': row})
                native_count += 1
        for process in encoders.values():
            process.stdin.close()
            if process.wait(timeout=180) != 0:
                raise RuntimeError('Source camera encoder failed')
        recorder.close(confirmed=True)
        recorder = None
        observed = measure(output / 'config.json', output / 'native.jsonl',
                           output / 'video_frames.jsonl', output / 'geometry.json')
        write_new(output / 'source-measurement.json', observed)
        write_result(output, {
            'measured_values': observed, 'target_checks': [{'target': 'pre_reference_halt',
                'requested': config.get('requested_halt'), 'measured': None,
                'method': 'independent original source review pending', 'tolerance': None,
                'matched': None, 'physical_cause_confirmed': False,
                'cause_evidence': 'original source review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False, 'termination_reason': 'source_review_pending',
            'physical_failure_flags': ['source_review_pending'],
            'trace_reference': 'native.jsonl',
            'video_references': [name + '.mkv' for name, _, _, _ in CAMERAS],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': config['recording_description'],
            'recording_evidence': derive_channels(output),
            'realized_observables': observed})
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
                errors.append('actor cleanup: ' + str(error))
        try:
            light.set_state(prior_light)
            restoration = restore(client, prior)
        except BaseException as error:
            errors.append('world restore: ' + str(error))
            restoration = None
        write_new(output / 'native-acquisition-report.json', {
            'case_id': case_id, 'observed_frames': native_count,
            'encoders_closed': all(p.poll() is not None for p in encoders.values()),
            'restoration': restoration, 'errors': errors,
            'physical_acceptance_claimed': False, 'legal_verdict': None})
        if errors:
            write_new(output / 'native-run-status.json', {
                'case_id': case_id, 'errors': errors, 'observed_frames': native_count,
                'physical_acceptance_claimed': False})
        if not errors and native_count == COUNT and restoration is not None:
            seal_capture(output, frames=COUNT, restoration=restoration, errors=[],
                         encoder_exit_codes={name: p.returncode for name, p in encoders.items()},
                         context={'case_id': case_id, 'source_review_pending': True})
