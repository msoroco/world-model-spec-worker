"""Original Native bicycle/motorist capture path for the exact C111294 bundle.

This module is imported only for an owned CARLA endpoint. CPU preflight uses
runner.check and never imports CARLA. Physical observations remain for the GPU.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from cameras import camera_plan
from engineering import parameters
from geometry import open_drive

FRAMES = 480


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: object) -> None:
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def camera_transform(carla, spec):
    x, y, z = spec['xyz_m']
    yaw = math.degrees(math.atan2(-y, -x))
    pitch = math.degrees(math.atan2(1.0-z, math.hypot(x, y)))
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw, pitch=pitch))


def original_row(index: int, frame: int, bicycle: dict, motor: dict,
                 brake_applied: bool) -> dict:
    """Normalize sampled actors without assuming synthetic body dimensions."""
    if type(index) is not int or type(frame) is not int or index < 0 or frame < 0:
        raise ValueError('Original frame identity absent')
    if bicycle['blueprint_id'] != 'vehicle.bh.crossbike' or not motor['blueprint_id'].startswith('vehicle.'):
        raise ValueError('Original actor blueprint differs')
    return {'frame': index, 'video_frame': index, 'native_frame': frame,
        'time_s': index/20,
        'bicycle': {'actor_id': bicycle['actor_id'], 'class': 'bicycle_blueprint_unverified_propulsion',
            'blueprint_id': bicycle['blueprint_id'], 'center_xy_m': bicycle['center_xy_m'],
            'body_xy_m': bicycle['body_xy_m'], 'speed_mps': bicycle['speed_mps']},
        'motor_vehicle': {'actor_id': motor['actor_id'], 'class': 'motor_vehicle',
            'blueprint_id': motor['blueprint_id'], 'center_xy_m': motor['center_xy_m'],
            'body_xy_m': motor['body_xy_m'], 'speed_mps': motor['speed_mps'],
            'brake_applied': bool(brake_applied)}}


def bicycle_velocity_x(current_x_m: float, forward_speed_mps: float,
                       lookahead_m: float) -> float:
    """Correct measured lane-center error; shorter fallback lookahead reacts sooner."""
    if lookahead_m <= 0 or forward_speed_mps < 0:
        raise ValueError('Invalid bicycle tracking controls')
    correction = (1.75-current_x_m)*forward_speed_mps/lookahead_m
    return max(-.6, min(.6, correction))


def motorist_hold(index: int, case: str, clearance_buffer_s: float) -> bool:
    """Extend the controlled motorist wait by the source-bound buffer knob."""
    if case not in ('witness_1','witness_2') or clearance_buffer_s < 1:
        raise ValueError('Invalid motorist clearance controls')
    return case=='witness_2' and 75 <= index < 250+round((clearance_buffer_s-1)*20)


def execute(config: dict, output: Path, host: str, port: int) -> dict:
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    from runner import check, sample

    check(config['case_suffix'], config['candidate_id'])
    expected=parameters(config['case_suffix'],config['candidate_id'])['knobs']
    if config.get('knobs')!=expected:
        raise ValueError('Exact candidate control knobs differ')
    output = output.resolve()
    if not output.is_dir() or not (output/'config.json').is_file() or (output/'road.xodr').exists():
        raise ValueError('Use a fresh exact materialized case directory; acquisition owns road.xodr')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('Requires exclusive idle asynchronous Native world')
    owned = []
    camera_queues = {}
    encoders = {}
    encoder_logs = {}
    channels = {}
    capture = None
    changed = False
    restored = None
    error = None
    frames = 0
    interaction_rows = []
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.25, max_road_length=50, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        for x, y, road, lane in ((1.75, -25, 1, -1), (-25, -1.75, 3, -1)):
            waypoint = mapping.get_waypoint(carla.Location(x=x, y=y, z=2),
                project_to_road=True, lane_type=carla.LaneType.Driving)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (road, lane):
                raise RuntimeError('Native actor spawn road/lane survey differs')
        blueprints = world.get_blueprint_library()
        bike_bp = blueprints.find('vehicle.bh.crossbike')
        bike_bp.set_attribute('role_name', 'c111294_bicycle_subject')
        bike = world.spawn_actor(bike_bp, carla.Transform(
            carla.Location(x=1.75, y=-25, z=1), carla.Rotation(yaw=90)))
        owned.append(bike)
        motor_bp = blueprints.find('vehicle.lincoln.mkz_2020')
        motor_bp.set_attribute('role_name', 'c111294_separate_motorist')
        motor = world.spawn_actor(motor_bp, carla.Transform(
            carla.Location(x=-25, y=-1.75, z=1), carla.Rotation(yaw=0)))
        owned.append(motor)
        write_new(output/'native-construction-context.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'bicycle_blueprint': bike.type_id, 'motor_vehicle_blueprint': motor.type_id,
            'rider_command': parameters(config['case_suffix'], config['candidate_id'])['rider_command'],
            'human_propulsion_physically_verified': False,
            'intent_or_legal_interference_verified': False})
        for camera in camera_plan(config['candidate_id']):
            bp = blueprints.find('sensor.camera.rgb')
            for key, value in (('image_size_x', camera['width']),
                               ('image_size_y', camera['height']),
                               ('fov', camera['fov_deg']), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, camera_transform(carla, camera))
            owned.append(sensor)
            camera_queues[camera['name']] = queue.Queue()
            sensor.listen(camera_queues[camera['name']].put)
            encoder_logs[camera['name']] = (output/(camera['name']+'.encoder.log')).open('x')
            encoders[camera['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f"{camera['width']}x{camera['height']}", '-r', '20', '-i', 'pipe:0',
                '-an', '-c:v', 'ffv1', '-level', '1', str(output/(camera['name']+'.mkv'))],
                stdin=subprocess.PIPE, stderr=encoder_logs[camera['name']])
            if camera['name']=='overview':
                pose=sensor.get_transform()
                write_new(output/'camera_context.json',{'name':'overview',
                    'width':camera['width'],'height':camera['height'],'fov_deg':camera['fov_deg'],
                    'pose':{'xyz_m':[pose.location.x,pose.location.y,pose.location.z],
                            'yaw_deg':pose.rotation.yaw,'pitch_deg':pose.rotation.pitch},
                    'source_kind':'original_native_camera_readback'})
        capture = PipelineCapture(client, bike, output, config['case_id'],
            visibility=False, required_observations=config.get('required_atoms', []))
        (output/'channels').mkdir()
        for channel in config['recording_description']['channels']:
            name = channel['name']
            channels[name] = (output/'channels'/(name+'.jsonl')).open('x')
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native_samples.jsonl').open('x') as native_file, \
             (output/'video_frames.jsonl').open('x') as video_map:
            for index in range(FRAMES):
                bike_target = 0. if config['case_suffix']=='witness_1' and 100<=index<190 else 2.6
                motor_hold = motorist_hold(index, config['case_suffix'],
                    config['knobs']['motorist_clearance_buffer_s'])
                bike_lateral = bicycle_velocity_x(bike.get_transform().location.x,
                    bike_target, config['knobs']['bicycle_route_tracking_lookahead_m'])
                bike.set_target_velocity(carla.Vector3D(x=bike_lateral, y=bike_target, z=0))
                motor.apply_control(carla.VehicleControl(throttle=0, brake=1 if motor_hold else 0))
                motor.set_target_velocity(carla.Vector3D(x=0 if motor_hold else 4, y=0, z=0))
                frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds-start
                bicycle = sample(bike, mapping, 'bicycle_blueprint_unverified_propulsion')
                vehicle = sample(motor, mapping, 'motor_vehicle')
                source_row = original_row(index, frame, bicycle, vehicle,
                    vehicle['control_brake'] >= .5)
                interaction_rows.append(source_row)
                capture.capture(frame, elapsed, extra={'c111294_native': source_row})
                body_vertices = bike.bounding_box.get_world_vertices(bike.get_transform())
                motor_vertices = motor.bounding_box.get_world_vertices(motor.get_transform())
                native = {'native_frame': frame, 'time_s': elapsed,
                    'bicycle': source_row['bicycle'], 'motor_vehicle': source_row['motor_vehicle'],
                    'bicycle_body_vertices_m': [[v.x, v.y, v.z] for v in body_vertices],
                    'motor_vehicle_body_vertices_m': [[v.x, v.y, v.z] for v in motor_vertices],
                    'requested_bicycle_speed_mps': bike_target,
                    'requested_bicycle_lateral_speed_mps': bike_lateral,
                    'requested_motor_hold': motor_hold,
                    'intent_or_legal_interference_claimed': False}
                native_file.write(json.dumps(native, allow_nan=False)+'\n')
                values = {'bicycle_body_pose': source_row['bicycle'],
                          'motorist_body_pose': source_row['motor_vehicle'],
                          'motorist_brake': source_row['motor_vehicle']['brake_applied'],
                          'camera_frame_join': {'native_frame': frame, 'video_frame': index}}
                for name, stream in channels.items():
                    stream.write(json.dumps({'time_s': elapsed, 'value': values[name]}, allow_nan=False)+'\n')
                for camera in camera_plan(config['candidate_id']):
                    image = camera_queues[camera['name']].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[camera['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Camera/Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        camera['height'], camera['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[camera['name']].stdin.write(rgb.tobytes())
                video_map.write(json.dumps({'video_frame': index, 'native_frame': frame,
                    'carla_frame': frame, 'time_s': elapsed})+'\n')
                frames += 1
        if frames != FRAMES:
            raise RuntimeError('Incomplete original capture frame count')
        interaction = {'format': 'c111294-cycle-motor-source-v1',
            'source_kind': 'original_native_and_video', 'law_id': 'NRS-484B-270-7a',
            'cell_id': 'C111294', 'actor': 'cycle_or_scooter_operator',
            'case': config['case_suffix'], 'map_sha256': sha(output/'road.xodr'),
            'rider_command_declared': 'hold_before_motorist_crosses' if config['case_suffix']=='witness_1'
                else 'enter_before_motorist_crosses',
            'intent_physically_verified': False, 'legal_interference_claimed': False,
            'frames': interaction_rows}
        write_new(output/'interaction.json', interaction)
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        for stream in channels.values():
            stream.close()
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
                if error is None:
                    manifest_path = output/'capture/manifest.json'
                    manifest = json.loads(manifest_path.read_text())
                    manifest['sources']['interaction.json'] = sha(output/'interaction.json')
                    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless camera encoder failed: '+name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        if error is None:
            try:
                from trigger_measure import SOURCES,measure as measure_triggers
                manifest_path=output/'capture/manifest.json'
                manifest=json.loads(manifest_path.read_text())
                for name in SOURCES:
                    manifest['sources'][name]=sha(output/name)
                manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
                write_new(output/'fallback-metrics.json',measure_triggers(output))
            except BaseException as exc:
                error={'trigger_measure_error':str(exc)}
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'owned_actor_cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        write_new(output/'native-capture-report.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'frames': frames, 'expected_frames': FRAMES,
            'restoration': restored, 'error': error, 'accepted': False,
            'physical_class_intent_pixels_verified': False})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json: '+str(error))
    return {'case_id': config['case_id'], 'frames': frames, 'accepted': False}
