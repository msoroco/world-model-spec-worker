"""Source-bound Native change-lane acquisition; physical and legal review remain open."""
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import traceback

from signal_scene import controls


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def control(carla, ego, target_y, gain):
    pose = ego.get_transform()
    velocity = ego.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    angle = math.atan2(target_y - pose.location.y, 18.0)
    error = math.atan2(math.sin(angle - math.radians(pose.rotation.yaw)),
                       math.cos(angle - math.radians(pose.rotation.yaw)))
    return carla.VehicleControl(steer=max(-.65, min(.65, gain * error)),
        throttle=max(0.0, min(.8, .2 + .2 * (5.0 - speed))),
        brake=max(0.0, min(.7, .35 * (speed - 5.0))))


def run(bundle, output, host, port):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Retain prior Native attempt; use fresh output')
    output.mkdir(parents=True)
    for name in ('config.json', 'road.xodr', 'assignment-source.json',
                 'construction.json', 'runner.py'):
        shutil.copyfile(bundle / name, output / name)
    write_new(output / 'acquisition-provenance.json', {
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'source_claim': 'original post-tick CARLA capture; legal and physical acceptance unverified'})
    root = next(parent for parent in Path(__file__).resolve().parents
                if (parent / 'batch.json').is_file())
    runtime_output = root / '.runtime-work' / 'c245490_native_runtime'
    runtime_output.mkdir(parents=True, exist_ok=True)
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(runtime_output)
    sys.path.insert(0, str(root / 'runtime/scenario_pipeline'))
    sys.path.insert(1, str(root / 'runtime/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.media import compose_four_views
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    config = json.loads((output / 'config.json').read_text())
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    original = client.get_world()
    if saved['settings'].synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.')) for actor in original.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned, encoders, logs, feeds = [], {}, {}, {}
    capture = None
    changed = False
    count = 0
    failure = None
    restored = None
    try:
        world = client.generate_opendrive_world((output / 'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.HardRainNoon if
            config['weather_requested'] == 'rain' else carla.WeatherParameters.ClearNoon)
        road_map = world.get_map()
        lanes = []
        for y, expected in ((-1.75, -1), (-5.25, -2)):
            waypoint = road_map.get_waypoint(carla.Location(x=-50, y=y, z=1),
                project_to_road=False, lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.lane_id != expected:
                raise RuntimeError('Original same-direction lane readback differs')
            lanes.append({'y_m': y, 'road_id': waypoint.road_id,
                          'lane_id': waypoint.lane_id})
        write_new(output / 'lane-source.json', {'lanes': lanes,
            'native_map_sha256': hashlib.sha256(road_map.to_opendrive().encode()).hexdigest(),
            'public_highway_verified': False})
        write_new(output / 'area-source.json', {'area_class_requested':
            config['area_class_requested'], 'area_class_originally_verified': False,
            'district_or_other_original_authority': None,
            'weather_requested': config['weather_requested'],
            'weather_originally_reviewed': False, 'legal_verdict': None})
        bp = world.get_blueprint_library().find(config['vehicle_blueprint'])
        bp.set_attribute('role_name', 'c245490_signal_subject')
        rightward = config['signal_side'] == 'right'
        start_lane, destination_lane = (-1, -2) if rightward else (-2, -1)
        start_y, destination_y = (-1.75, -5.25) if rightward else (-5.25, -1.75)
        ego = world.try_spawn_actor(bp, carla.Transform(
            carla.Location(x=-90, y=start_y, z=1.5), carla.Rotation(yaw=0)))
        if ego is None:
            raise RuntimeError('Original change-lane ego unavailable')
        owned.append(ego)
        for _ in range(20):
            world.tick()
        for camera in config['cameras']:
            name, width, height = camera['name'], camera['width'], camera['height']
            sensor_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', camera['fov_deg']), ('sensor_tick', 0)):
                sensor_bp.set_attribute(key, str(value))
            xyz = camera['xyz_m']
            transform = carla.Transform(carla.Location(*xyz),
                carla.Rotation(yaw=camera['yaw_deg'], pitch=camera['pitch_deg']))
            sensor = world.spawn_actor(sensor_bp, transform,
                attach_to=ego if camera['attach_to_ego'] else None)
            owned.append(sensor)
            feeds[name] = queue.Queue()
            logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f'{width}x{height}', '-r', '20', '-i', 'pipe:0', '-an',
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=logs[name])
            sensor.listen(feeds[name].put)
        capture = PipelineCapture(client, ego, output, config['selected_case_id'],
            visibility=False, required_observations=[])
        previous = ego.get_location()
        odometer = 0.0
        prior_lane = start_lane
        with (output / 'signal-source.jsonl').open('x') as signal, \
             (output / 'body_history.jsonl').open('x') as body_history, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(600):
                request = controls(config['selected_case_id'].rsplit('__', 1)[-1], odometer)
                blink = (carla.VehicleLightState.RightBlinker if rightward else
                    carla.VehicleLightState.LeftBlinker)
                ego.set_light_state(blink if request['signal_requested'] else
                    carla.VehicleLightState.NONE)
                ego.apply_control(control(carla, ego, destination_y if
                    request['lane_change_requested'] else start_y,
                    config['controller_gain']))
                native_frame = world.tick()
                pose = ego.get_transform()
                location = pose.location
                odometer += math.hypot(location.x - previous.x,
                                       location.y - previous.y)
                previous = location
                waypoint = road_map.get_waypoint(location, project_to_road=False,
                    lane_type=carla.LaneType.Driving)
                lane = None if waypoint is None else waypoint.lane_id
                changed_lane = prior_lane == start_lane and lane == destination_lane
                prior_lane = lane
                lights = int(ego.get_light_state())
                time_s = world.get_snapshot().timestamp.elapsed_seconds
                vertices = [[point.x, point.y, point.z] for point in
                    ego.bounding_box.get_world_vertices(pose)]
                row = {'frame': index, 'original_carla_frame': native_frame,
                    'time_s': index * .05, 'original_time_s': time_s,
                    'ego_xy_m': [location.x, location.y],
                    'native_yaw_deg': pose.rotation.yaw, 'native_lane_id': lane,
                    'observed_odometer_m': odometer,
                    'turn_indicator': config['signal_side'] if lights & int(blink) else 'off',
                    'course_change': changed_lane,
                    'signal_requested': request['signal_requested'],
                    'lane_change_requested': request['lane_change_requested'],
                    'source_kind': 'original_post_tick_native',
                    'visible_signal_pixels_reviewed': False}
                capture.capture(native_frame, index * .05,
                    extra={'c245490_signal': row})
                signal.write(json.dumps(row, allow_nan=False) + '\n')
                body_history.write(json.dumps({'frame': native_frame,
                    'time_s': index * .05, 'body_vertices_m': vertices,
                    'lane_id': lane, 'heading_deg': pose.rotation.yaw},
                    allow_nan=False) + '\n')
                for camera in config['cameras']:
                    name, width, height = camera['name'], camera['width'], camera['height']
                    image = feeds[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = feeds[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera/Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame': index,
                    'native_frame': native_frame, 'carla_frame': native_frame,
                    'time_s': index * .05}, allow_nan=False) + '\n')
                count += 1
    except BaseException as exc:
        failure = {'type': type(exc).__name__, 'message': str(exc),
                   'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=failure is None)
            except BaseException as exc:
                failure = failure or {'capture_close_error': str(exc)}
        for name, process in encoders.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: ' + name)
            except BaseException as exc:
                failure = failure or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                failure = failure or {'cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                failure = failure or {'restore_error': str(exc)}
        if failure is None and count == 600:
            try:
                sources = {item['name']: output / (item['name'] + '.mkv')
                           for item in config['cameras']}
                receipt = compose_four_views(sources, output / 'video_frames.jsonl',
                                             output / 'raw.mkv')
                write_new(output / 'four-view-receipt.json', receipt)
                seal_capture(output, frames=count, restoration=restored, errors=[],
                    encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                    context={'case_id': config['selected_case_id'],
                             'area_class_originally_verified': False,
                             'visible_indicator_pixels_reviewed': False,
                             'legal_verdict': None})
            except BaseException as exc:
                failure = failure or {'seal_error': str(exc)}
        write_new(output / 'native-capture-report.json', {
            'case_id': config['selected_case_id'], 'requested_frames': 600,
            'observed_frames': count, 'restoration': restored,
            'error': failure, 'accepted': False, 'legal_verdict': None})
    if failure:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')
