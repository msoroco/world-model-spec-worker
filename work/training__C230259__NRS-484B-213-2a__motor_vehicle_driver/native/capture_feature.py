"""Prospective CARLA acquisition for exact crest/curve and one-way cases.

CARLA and runtime modules load only inside execute. Native observations and
actual pixels are retained for independent review; no legal result is emitted.
"""
import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import traceback

CAMERAS = (('overview', 1920, 1080, 90, (0, 0, 36), -90),
           ('approach', 1280, 720, 85, (4, 0, 2), -8),
           ('reference_corner', 1280, 720, 85, (0, 6, 7), -30),
           ('driver_reference', 1280, 720, 90, (1, 0, 1.5), 0))


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


def steer(carla, ego, target, speed_mps):
    pose = ego.get_transform()
    velocity = ego.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    location = target.transform.location
    desired = math.atan2(location.y - pose.location.y, location.x - pose.location.x)
    current = math.radians(pose.rotation.yaw)
    error = math.atan2(math.sin(desired-current), math.cos(desired-current))
    return carla.VehicleControl(
        steer=max(-.7, min(.7, 1.4 * error)),
        throttle=max(0, min(1, .22 + .23 * (speed_mps-speed))),
        brake=max(0, min(1, .35 * (speed-speed_mps))))


def phase(config, index):
    selected = [part for part in config['control_phases']
                if part['first_frame'] <= index <= part['last_frame']]
    if len(selected) != 1:
        raise ValueError('Missing or overlapping exact control phase')
    return selected[0]


def source_row(world, mapping, ego, other, frame, native_frame, time_s, config):
    pose = ego.get_transform()
    velocity = ego.get_velocity()
    waypoint = mapping.get_waypoint(pose.location, project_to_road=False,
                                    lane_type=__import__('carla').LaneType.Driving)
    if waypoint is None or waypoint.road_id != 1:
        raise RuntimeError('Ego left the requested Native road')
    center = mapping.get_waypoint_xodr(1, int(config['ego_lane_id']), waypoint.s)
    if center is None:
        raise RuntimeError('Missing Native map centerline readback')
    right = center.transform.get_right_vector()
    offset = 1.75
    center_point = center.transform.location
    center_x, center_y = center_point.x - right.x*offset, center_point.y - right.y*offset
    forward = center.transform.get_forward_vector()
    vertices = ego.bounding_box.get_world_vertices(pose)
    signed = [-(forward.x*(point.y-center_y)-forward.y*(point.x-center_x)) for point in vertices]
    if len(vertices) != 8:
        raise RuntimeError('Missing original eight-corner ego body')
    other_pose = other.get_transform()
    driver_eye = pose.transform(__import__('carla').Location(x=1, y=0, z=1.5))
    ahead = center.transform.get_forward_vector()
    end = driver_eye + __import__('carla').Location(x=250*ahead.x, y=250*ahead.y, z=250*ahead.z)
    if not hasattr(world, 'cast_ray'):
        raise RuntimeError('Native cast_ray sightline API unavailable')
    hits = list(world.cast_ray(driver_eye, end))
    distances = [driver_eye.distance(hit.location) for hit in hits if hasattr(hit, 'location')]
    sight_clear = min(distances, default=250.0)
    return {'frame': frame, 'native_frame': native_frame, 'time_s': time_s,
            'ego_id': ego.id, 'ego_s_m': waypoint.s,
            'ego_forward_mps': velocity.x*ahead.x + velocity.y*ahead.y,
            'ego_body_min_signed_m': min(signed), 'ego_body_max_signed_m': max(signed),
            'ego_body_native_xyz_m': [[v.x, v.y, v.z] for v in vertices],
            'ego_transform_native_xyz_yaw': [pose.location.x, pose.location.y, pose.location.z, pose.rotation.yaw],
            'sight_clear_m': sight_clear, 'sight_censored': not distances,
            'available_forward_road_m': 250.0,
            'camera_frame_ids': {name: frame for name, *_ in CAMERAS},
            'map_waypoint_source': [waypoint.road_id, waypoint.lane_id, waypoint.s],
            'other_vehicle_id': other.id,
            'other_vehicle_route_direction': config['other_vehicle']['route_direction'],
            'other_vehicle_s_m': mapping.get_waypoint(other_pose.location, project_to_road=True).s,
            'other_vehicle_transform_native_xyz_yaw': [other_pose.location.x, other_pose.location.y, other_pose.location.z, other_pose.rotation.yaw],
            'source_kind': 'original_native', 'physical_verified': False,
            'legal_verdict': None}


def execute(bundle, output, host, port, checked):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    if output.exists():
        if not output.is_dir() or not (output / 'config.json').is_file() or sha(output / 'config.json') != sha(bundle / 'config.json'):
            raise ValueError('Native output is not the materialized exact case')
    else:
        output.mkdir(parents=True)
        shutil.copyfile(bundle / 'config.json', output / 'config.json')
    repo = repository()
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    sys.path.insert(1, str(repo / 'runtime/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.media import compose_four_views
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore
    config = json.loads((bundle / 'config.json').read_text())
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    old_state = snapshot(client)
    old_world = client.get_world()
    if old_state['settings'].synchronous_mode or any(
            a.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for a in old_world.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, encoders, encoder_logs, camera_queues = [], {}, {}, {}
    capture, changed, frames, restored, error = None, False, 0, None, None
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
        base_lane = int(config['ego_lane_id'])
        ego_waypoint = mapping.get_waypoint_xodr(1, base_lane, float(config['ego_spawn']['s_m']))
        other_spec = config['other_vehicle']
        other_waypoint = mapping.get_waypoint_xodr(1, int(other_spec['lane_id']), float(other_spec['spawn_s_m']))
        if ego_waypoint is None or other_waypoint is None:
            raise RuntimeError('Generated Native lanes are missing')
        lib = world.get_blueprint_library()
        ego_bp, other_bp = lib.find('vehicle.tesla.model3'), lib.find('vehicle.audi.tt')
        ego_bp.set_attribute('role_name', 'c230259_ego')
        other_bp.set_attribute('role_name', 'c230259_other')
        ego_pose, other_pose = ego_waypoint.transform, other_waypoint.transform
        ego_pose.location.z += 1.0
        other_pose.location.z += 1.0
        ego = world.try_spawn_actor(ego_bp, ego_pose)
        other = world.try_spawn_actor(other_bp, other_pose)
        if ego is None or other is None:
            raise RuntimeError('Exact ego/other Native spawn failed')
        owned += [ego, other]
        for _ in range(20):
            world.tick()
        map_text = mapping.to_opendrive()
        write_new(output / 'road-context.json', {
            'feature_kind': 'curve' if 'curve' in config['case_id'] else 'crest',
            'feature_start_s_m': 300.0 if 'curve' in config['case_id'] else 450.0,
            'feature_end_s_m': 600.0,
            'road_geometry_sha256': hashlib.sha256(map_text.encode()).hexdigest(),
            'road_geometry_source': {'kind': 'original Native map readback',
                                     'sha256': hashlib.sha256(map_text.encode()).hexdigest()},
            'directionality': config['road_directionality'],
            'directionality_claim_source': 'authored OpenDRIVE plus Native lane readback; public authority pending',
            'centerline_source': 'original Native lane waypoint at each ego frame',
            'grade_profile_source': 'original Native map elevation readback' if 'curve' not in config['case_id'] else None,
            'curvature_source': 'original Native planView arc readback' if 'curve' in config['case_id'] else None,
            'legal_highway_authority_verified': False,
            'source_kind': 'original_native_map_readback_pending_review'})
        for name, width, height, fov, location, pitch in CAMERAS:
            bp = lib.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', fov), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            x, y, z = location
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=pitch)), attach_to=ego)
            owned.append(sensor)
            camera_queues[name] = queue.Queue()
            encoder_logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', '20',
                '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=encoder_logs[name])
            sensor.listen(camera_queues[name].put)
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False, required_observations=[])
        start_time = world.get_snapshot().timestamp.elapsed_seconds + .05
        with (output / 'native-feature-source.jsonl').open('x') as stream, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(600):
                selected = phase(config, index)
                current = mapping.get_waypoint(ego.get_transform().location, project_to_road=True)
                target_s = min(float(current.s) + 12, 890)
                target = mapping.get_waypoint_xodr(1, int(selected['target_lane_id']), target_s)
                if target is None:
                    raise RuntimeError('Selected lane target unavailable in Native map')
                ego.apply_control(steer(carla, ego, target, selected['target_speed_mps']))
                native_frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start_time
                row = source_row(world, mapping, ego, other, index, native_frame, time_s, config)
                row['requested_lane_id'] = selected['target_lane_id']
                capture.capture(native_frame, time_s, extra={'c230259_feature': row})
                for name, width, height, *_ in CAMERAS:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera/Native source frame misjoin')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                frame_map.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s}, allow_nan=False) + '\n')
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
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
                    raise RuntimeError('Lossless camera encoder failed: ' + name)
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
                restored = restore(client, old_state)
            except BaseException as exc:
                error = error or {'restore_error': str(exc)}
        if error is None and frames == 600:
            try:
                videos = {name: output / (name + '.mkv') for name, *_ in CAMERAS}
                write_new(output / 'four-view-receipt.json',
                          compose_four_views(videos, output / 'video_frames.jsonl', output / 'raw.mkv'))
                seal_capture(output, frames=frames, restoration=restored, errors=[],
                    encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                    context={'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
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
