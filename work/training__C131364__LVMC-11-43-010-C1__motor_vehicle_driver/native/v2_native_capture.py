"""Attempt the source-pinned 600-frame roundabout requests in an idle Native world.

This creates original readbacks for later independent review. It never asserts
that the roundabout, lane occupancy, intended exit, or legal outcome succeeded.
"""
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

from v2_runner import check


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repository():
    override = os.environ.get('SCENARIO_REPO_ROOT')
    if override and (Path(override) / 'runtime').is_dir():
        return Path(override).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / 'batch.json').is_file() and (parent / 'runtime').is_dir():
            return parent
    raise ValueError('Pinned runtime repository unavailable')


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def actor_pose(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    body = actor.bounding_box.get_world_vertices(transform)
    return {'actor_id': actor.id, 'blueprint': actor.type_id,
        'center_native_xyz_m': [transform.location.x, transform.location.y, transform.location.z],
        'yaw_deg': transform.rotation.yaw,
        'velocity_native_xyz_mps': [velocity.x, velocity.y, velocity.z],
        'speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
        'body_native_xyz_m': [[v.x, v.y, v.z] for v in body]}


def control_to(carla, actor, target, requested_speed):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    error = math.atan2(target['ego_y_m'] - transform.location.y,
                       target['ego_x_m'] - transform.location.x) - math.radians(transform.rotation.yaw)
    error = math.atan2(math.sin(error), math.cos(error))
    return carla.VehicleControl(
        steer=max(-.75, min(.75, 1.6 * error)),
        throttle=max(0, min(1, .22 + .22 * (requested_speed - speed))),
        brake=max(0, min(1, .4 * (speed - requested_speed))))


def camera_transform(carla, name):
    if name == 'overview':
        return carla.Transform(carla.Location(x=10, y=-15, z=35),
                               carla.Rotation(pitch=-55)), False
    if name == 'approach':
        return carla.Transform(carla.Location(x=-5, y=0, z=8),
                               carla.Rotation(pitch=-35)), True
    if name == 'reference_corner':
        return carla.Transform(carla.Location(x=5, y=4, z=6),
                               carla.Rotation(pitch=-25)), True
    if name == 'driver_reference':
        return carla.Transform(carla.Location(x=1, y=0, z=1.5)), True
    raise ValueError('Unknown camera: ' + name)


def execute(bundle, output, host, port):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    checked = check(bundle)
    if not output.is_dir() or output != bundle:
        raise ValueError('Native capture needs its materialized attempt directory')
    if any((output / name).exists() for name in ('native-raw-actors.jsonl',
            'native-capture-report.json', 'video_frames.jsonl')):
        raise ValueError('Native capture outputs already exist')
    repo = repository()
    expected_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not expected_root or not Path(expected_root).resolve().is_relative_to(repo / '.runtime-work'):
        raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work')
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    sys.path.insert(0, str(repo / 'runtime/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import seal_capture

    config = json.loads((bundle / 'config.json').read_text())
    # PipelineCapture exports the generated map at road.xodr. Keep the authored
    # OpenDRIVE bytes separately so the original request remains inspectable.
    with (output / 'authored-road.xodr').open('x') as stream:
        stream.write((bundle / 'road.xodr').read_text())
    requests = [json.loads(line) for line in (bundle / 'authored-route.jsonl').read_text().splitlines()]
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned, video, logs, queues = [], {}, {}, {}
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
        lane_readback = {}
        for phase in ('entry', 'circulation', 'exit'):
            phase_rows = [row for row in requests if row['phase'] == phase]
            sample = phase_rows[len(phase_rows) // 2]
            waypoint = mapping.get_waypoint(carla.Location(x=sample['ego_x_m'],
                y=sample['ego_y_m'], z=1), project_to_road=False,
                lane_type=carla.LaneType.Driving)
            lane_readback[phase] = None if waypoint is None else {
                'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id}
            if waypoint is None or waypoint.road_id != sample['road_id'] or waypoint.lane_id != sample['lane_id']:
                raise RuntimeError('Generated Native road/lane readback differs at ' + phase)
        first = requests[0]
        library = world.get_blueprint_library()
        blueprint = library.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name', 'c131364_ego')
        ego = world.try_spawn_actor(blueprint, carla.Transform(
            carla.Location(x=first['ego_x_m'], y=first['ego_y_m'], z=1.5),
            carla.Rotation(yaw=first['ego_heading_deg'])))
        if ego is None:
            raise RuntimeError('C131364 ego spawn failed')
        owned.append(ego)
        for _ in range(20):
            world.tick()
        write_new(output / 'native-map-readback.json', {
            'road_sha256': sha(bundle / 'road.xodr'),
            'native_map_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'phase_lane_readback': lane_readback, 'ego_actor_id': ego.id,
            'physical_roundabout_verified': False, 'lane_allocation_reviewed': False,
            'actual_left_exit_verified': False, 'legal_verdict': None})
        cameras = config['cameras']
        for camera in cameras:
            name, width, height = camera['name'], camera['width'], camera['height']
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            transform, attached = camera_transform(carla, name)
            sensor = world.spawn_actor(bp, transform, attach_to=ego if attached else None)
            owned.append(sensor)
            queues[name] = queue.Queue()
            logs[name] = (output / (name + '.encoder.log')).open('x')
            video[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=logs[name])
            sensor.listen(queues[name].put)
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False, required_observations=[])
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native-raw-actors.jsonl').open('x') as observed, \
             (output / 'roundabout-track.jsonl').open('x') as route, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for i, request in enumerate(requests):
                lookahead = requests[min(len(requests) - 1, i + 12)]
                ego.apply_control(control_to(carla, ego, lookahead, 6))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                transform = ego.get_transform()
                waypoint = mapping.get_waypoint(transform.location, project_to_road=False,
                    lane_type=carla.LaneType.Driving)
                row = {'frame': i, 'native_frame': frame, 'time_s': time_s,
                    'source_kind': 'original_native', 'requested_phase': request['phase'],
                    'requested_road_id': request['road_id'],
                    'requested_lane_id': request['lane_id'],
                    'observed_road_id': None if waypoint is None else waypoint.road_id,
                    'observed_lane_id': None if waypoint is None else waypoint.lane_id,
                    'ego': actor_pose(ego), 'physical_roundabout_verified': False,
                    'actual_left_exit_verified': False, 'legal_verdict': None}
                capture.capture(frame, time_s, extra={'c131364_connected_exit': row})
                observed.write(json.dumps(row, allow_nan=False) + '\n')
                route.write(json.dumps({'frame': i, 'native_frame': frame,
                    'time_s': time_s, 'source_kind': 'original_native',
                    'requested_phase': request['phase'],
                    'requested_road_id': request['road_id'],
                    'requested_lane_id': request['lane_id'],
                    'observed_road_id': row['observed_road_id'],
                    'observed_lane_id': row['observed_lane_id'],
                    'ego_x_m': transform.location.x, 'ego_y_m': transform.location.y,
                    'ego_heading_deg': transform.rotation.yaw,
                    'actual_exit_observed': False,
                    'roundabout_verified': False}, allow_nan=False) + '\n')
                for camera in cameras:
                    name, width, height = camera['name'], camera['width'], camera['height']
                    image = queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Camera/Native frame join differs: ' + name)
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    video[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame': i, 'native_frame': frame,
                    'time_s': time_s}, allow_nan=False) + '\n')
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
        for name, process in video.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
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
        if sha(output / 'authored-road.xodr') != config['road_sha256']:
            error = error or {'source_error': 'Authored OpenDRIVE bytes changed'}
        write_new(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'construction_sha256': sha(bundle / 'config.json'),
            'requested_frames': 600, 'observed_frames': frames,
            'restoration': restored, 'error': error, 'accepted': False,
            'physical_roundabout_verified': False, 'lane_allocation_reviewed': False,
            'actual_left_exit_verified': False, 'legal_verdict': None,
            'delivery_ready': False})
        write_new(output / 'native-run-status.json', {
            'format': 'worker-native-run-status', 'case_id': config['case_id'],
            'frames': frames, 'errors': [] if error is None else [error],
            'restoration': restored, 'accepted': False})
        if error is None:
            write_new(output / 'acquisition-provenance.json', {
                'provenance_kind': 'native', 'diagnostic_fixture': False,
                'case_id': config['case_id'], 'source': 'original CARLA run'})
            seal_capture(output, frames=frames, restoration=restored, errors=[],
                encoder_exit_codes={name: process.returncode for name, process in video.items()},
                context={'authored_road_sha256': config['road_sha256'],
                         'observed_map_readback': 'native-map-readback.json'})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')
    return checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(Path.cwd())))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Native capture requires --output-dir, --host and --port')
        print(json.dumps(execute(Path.cwd(), args.output_dir, args.host, args.port)))
