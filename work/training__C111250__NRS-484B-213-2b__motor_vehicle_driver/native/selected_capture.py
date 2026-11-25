"""Original Native acquisition for the three exact straight-through requests."""
import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import traceback


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repository():
    for parent in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents):
        if (parent / 'batch.json').is_file() and (parent / 'runtime').is_dir():
            return parent
    raise ValueError('Pinned runtime repository unavailable')


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def camera_plan():
    return (('overview', 1920, 1080, 85, (0, 0, 38), 'world'),
            ('approach', 1280, 720, 80, (-36, -17, 8), 'world'),
            ('reference_corner', 1280, 720, 85, (13, 18, 11), 'world'),
            ('driver_reference', 1280, 720, 90, (1, 0, 1.5), 'ego'))


def body_row(ego, index, native_frame, time_s, waypoint):
    transform = ego.get_transform()
    velocity = ego.get_velocity()
    vertices = ego.bounding_box.get_world_vertices(transform)
    footprint = sorted({(round(v.x, 6), round(v.y, 6)) for v in vertices})
    if len(footprint) != 4:
        raise RuntimeError('Original Native body has no four-corner footprint')
    return {'frame': index, 'native_frame': native_frame, 'time_s': time_s,
            'actor_id': ego.id, 'blueprint': ego.type_id,
            'center_native_xyz_m': [transform.location.x, transform.location.y, transform.location.z],
            'yaw_deg': transform.rotation.yaw,
            'velocity_native_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'body_native_xyz_m': [[v.x, v.y, v.z] for v in vertices],
            'body_xy_m': [list(p) for p in footprint],
            'observed_road_id': None if waypoint is None else waypoint.road_id,
            'observed_lane_id': None if waypoint is None else waypoint.lane_id,
            'source_kind': 'original_native', 'physical_highway_verified': False,
            'legal_verdict': None}


def steering(carla, ego, x_target, y_target, speed_target):
    transform = ego.get_transform()
    velocity = ego.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    angle = math.atan2(y_target - transform.location.y, x_target - transform.location.x)
    error = math.atan2(math.sin(angle - math.radians(transform.rotation.yaw)),
                       math.cos(angle - math.radians(transform.rotation.yaw)))
    return carla.VehicleControl(steer=max(-0.7, min(0.7, 1.5 * error)),
                                throttle=max(0.0, min(1.0, 0.22 + 0.22 * (speed_target - speed))),
                                brake=max(0.0, min(1.0, 0.4 * (speed - speed_target))))


def execute(bundle, output, host, port, checked):
    bundle = Path(bundle).resolve()
    output = Path(output).resolve()
    if output.exists():
        if not output.is_dir() or not (output / 'config.json').is_file() or sha(output / 'config.json') != sha(bundle / 'config.json'):
            raise ValueError('Native output is not the materialized exact case')
    else:
        output.mkdir(parents=True)
        shutil.copyfile(bundle / 'config.json', output / 'config.json')
    root = repository()
    sys.path.insert(0, str(root / 'runtime/scenario_pipeline'))
    sys.path.insert(1, str(root / 'runtime/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.media import compose_four_views
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore
    config = json.loads((bundle / 'config.json').read_text())
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned = []
    encoders = {}
    encoder_logs = {}
    camera_queues = {}
    capture = None
    changed = False
    frames = 0
    restored = None
    error = None
    try:
        world = client.generate_opendrive_world((bundle / 'road.xodr').read_text(),
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
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        lanes = []
        for x, lane in ((-55, -1), (-55, 1), (25, -1)):
            point = carla.Location(x=x, y=-1.75 if lane == -1 else 1.75, z=1.0)
            waypoint = mapping.get_waypoint(point, project_to_road=False,
                                            lane_type=carla.LaneType.Driving)
            lanes.append({'x_m': x, 'requested_lane_id': lane,
                          'observed_road_id': None if waypoint is None else waypoint.road_id,
                          'observed_lane_id': None if waypoint is None else waypoint.lane_id})
            if waypoint is None or waypoint.lane_id != lane:
                raise RuntimeError('Generated two-way Native lane readback differs')
        library = world.get_blueprint_library()
        blueprint = library.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name', 'c111250_ego')
        ego = world.try_spawn_actor(blueprint, carla.Transform(
            carla.Location(x=-70, y=-1.75, z=1.5), carla.Rotation(yaw=0)))
        if ego is None:
            raise RuntimeError('C111250 ego spawn failed')
        owned.append(ego)
        for _ in range(20):
            world.tick()
        write_new(output / 'native-map-readback.json', {
            'road_sha256': sha(bundle / 'road.xodr'),
            'native_map_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'lane_readback': lanes, 'ego_actor_id': ego.id,
            'physical_highway_verified': False, 'intersection_definition_verified': False,
            'legal_verdict': None})
        write_new(output / 'road-context.json', {
            'approach_axis_xy': [1, 0], 'centerline_y_m': 0,
            'intersection_x_m': [-7, 7], 'one_way_highway': False,
            'two_way_intersection_source': True,
            'source_kind': 'original_native_map_readback_pending_review',
            'road_sha256': sha(bundle / 'road.xodr'),
            'native_map_readback_sha256': sha(output / 'native-map-readback.json'),
            'physical_roadway_verified': False})
        cameras = camera_plan()
        for name, width, height, fov, location, attachment in cameras:
            camera_bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', fov), ('sensor_tick', 0)):
                camera_bp.set_attribute(key, str(value))
            x, y, z = location
            if attachment == 'world':
                yaw = math.degrees(math.atan2(-y, -x))
                pitch = math.degrees(math.atan2(-z, math.hypot(x, y)))
            else:
                yaw = 0
                pitch = 0
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                        carla.Rotation(pitch=pitch, yaw=yaw))
            sensor = world.spawn_actor(camera_bp, transform,
                                       attach_to=ego if attachment == 'ego' else None)
            owned.append(sensor)
            camera_queues[name] = queue.Queue()
            encoder_logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=encoder_logs[name])
            sensor.listen(camera_queues[name].put)
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False, required_observations=[])
        start = world.get_snapshot().timestamp.elapsed_seconds + .05
        left = config['requested_left_interval']
        with (output / 'native-raw-actors.jsonl').open('x') as observed, \
             (output / 'vehicle-footprints.jsonl').open('x') as footprints, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(600):
                requested_left = bool(left and left[0] <= index <= left[1])
                speed = config['requested_speed_mps']
                ego.apply_control(steering(carla, ego, -70 + speed * (index + 12) / 20,
                                           1.75 if requested_left else -1.75, speed))
                native_frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                waypoint = mapping.get_waypoint(ego.get_transform().location,
                    project_to_road=False, lane_type=carla.LaneType.Driving)
                row = body_row(ego, index, native_frame, time_s, waypoint)
                row['requested_left'] = requested_left
                row['case_id'] = config['case_id']
                capture.capture(native_frame, time_s, extra={'c111250_centerline': row})
                observed.write(json.dumps(row, allow_nan=False) + '\n')
                footprints.write(json.dumps({
                    'native_frame': index, 'original_carla_frame': native_frame,
                    'time_s': time_s, 'body_xy_m': row['body_xy_m'],
                    'source_kind': 'original_native'}, allow_nan=False) + '\n')
                for name, width, height, _, _, _ in cameras:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera/Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame': index,
                    'native_frame': native_frame, 'time_s': time_s}, allow_nan=False) + '\n')
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, process in encoders.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'restore_error': str(exc)}
        if error is None and frames == 600:
            try:
                sources = {name: output / (name + '.mkv') for name, _, _, _, _, _ in cameras}
                receipt = compose_four_views(sources, output / 'video_frames.jsonl',
                                             output / 'raw.mkv')
                write_new(output / 'four-view-receipt.json', receipt)
                seal_capture(output, frames=frames, restoration=restored, errors=[],
                    encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                    context={'case_id': config['case_id'],
                             'candidate_id': config['candidate_id'],
                             'physical_acceptance_claimed': False})
            except BaseException as exc:
                error = error or {'seal_error': str(exc)}
        write_new(output / 'native-capture-report.json', {
            'case_id': checked['case_id'], 'candidate_id': config['candidate_id'],
            'bundle_config_sha256': sha(bundle / 'config.json'),
            'requested_frames': 600, 'observed_frames': frames,
            'restoration': restored, 'error': error, 'accepted': False,
            'physical_highway_verified': False, 'legal_verdict': None})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')
