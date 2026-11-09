"""Unaccepted original CARLA attempt for the C10389 device comparison."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from check import check
from build import FRAMES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def body(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    points = actor.bounding_box.get_world_vertices(transform)
    return {'actor_id': actor.id, 'blueprint': actor.type_id,
            'center_native_xyz_m': [transform.location.x, transform.location.y,
                                    transform.location.z],
            'velocity_native_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'speed_mps': math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
            'body_native_xyz_m': [[p.x, p.y, p.z] for p in points]}


def capture(bundle, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    bundle = Path(bundle).resolve()
    output = Path(output).resolve()
    checked = check(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    requests = [json.loads(row) for row in
                (bundle / 'requested-tracks.jsonl').read_text().splitlines()]
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    saved = snapshot(client)
    if prior.get_settings().synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in prior.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    output.mkdir(parents=True, exist_ok=False)
    owned, encoders, logs, queues = [], {}, {}, {}
    changed = False
    frames = 0
    error = None
    restored = None
    landmark_verified = False
    pipeline = None
    try:
        world = client.generate_opendrive_world((bundle / 'alley-stop.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
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
        lane_rows = {}
        for x in (20, 45, 55):
            wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1),
                project_to_road=False, lane_type=carla.LaneType.Any)
            lane_rows[str(x)] = None if wp is None else {
                'road_id': wp.road_id, 'lane_id': wp.lane_id,
                'lane_type': 'driving' if wp.lane_type == carla.LaneType.Driving else 'other'}
            if wp is None or wp.road_id != 389 or wp.lane_id != -1 or \
                    wp.lane_type != carla.LaneType.Driving:
                raise RuntimeError('Generated alley lane differs')
        landmarks = [{'id': str(item.id), 'road_id': int(item.road_id),
                      's_m': float(item.s), 'type': str(item.type)}
                     for item in mapping.get_all_landmarks()]
        matches = [item for item in landmarks if item['id'] == '3891' and
                   item['road_id'] == 389 and abs(item['s_m'] - 50) < .5 and
                   item['type'] == '206']
        if len(matches) != 1:
            raise RuntimeError('Generated OpenDRIVE stop landmark absent or ambiguous')
        landmark_verified = True
        bp = world.get_blueprint_library().find('vehicle.tesla.model3')
        bp.set_attribute('role_name', 'c10389_ego')
        ego = world.try_spawn_actor(bp, carla.Transform(carla.Location(x=5, y=-1.75, z=1.5)))
        if ego is None:
            raise RuntimeError('C10389 ego spawn failed')
        owned.append(ego)
        elevated = cfg['camera_policy'] == 'elevated_overview'
        specs = (('overview', 1280, 720, 100 if elevated else 85,
                  (50, -15, 45 if elevated else 30), -70 if elevated else -60),
                 ('forward', 1280, 720, 90, (1, 0, 1.5), 0))
        for name, width, height, fov, location, pitch in specs:
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', fov), ('sensor_tick', 0)):
                camera_bp.set_attribute(key, str(value))
            camera = world.spawn_actor(camera_bp,
                carla.Transform(carla.Location(*location), carla.Rotation(pitch=pitch)),
                attach_to=ego if name == 'forward' else None)
            owned.append(camera)
            queues[name] = queue.Queue()
            camera.listen(queues[name].put)
            logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f'{width}x{height}', '-r', '20', '-i', 'pipe:0', '-an',
                '-c:v', 'ffv1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=logs[name])
        write_new(output / 'native-map-readback.json', {
            'source_kind': 'original_native',
            'road_sha256': sha(bundle / 'alley-stop.xodr'),
            'native_map_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'lane_readback': lane_rows, 'stop_landmark_readback': matches[0],
            'stop_landmark_verified': landmark_verified,
            'ego_actor_id': ego.id,
            'official_placement_verified': False,
            'police_direction_verified': False,
            'signal_specific_exception_reviewed': False,
            'legal_verdict': None})
        for _ in range(20):
            world.tick()
        pipeline = PipelineCapture(client, ego, output, cfg['case_id'], visibility=False)
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native-raw-actors.jsonl').open('x') as actors, \
             (output / 'video_frames.jsonl').open('x') as videos:
            for i, requested in enumerate(requests):
                ego.set_target_velocity(carla.Vector3D(x=requested['requested_speed_mps'],
                                                       y=0, z=0))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                wp = mapping.get_waypoint(ego.get_transform().location,
                    project_to_road=False, lane_type=carla.LaneType.Any)
                row = {'frame': i, 'native_frame': frame, 'time_s': time_s,
                    'source_kind': 'original_native',
                    'requested_ego_x_m': requested['requested_ego_x_m'],
                    'requested_speed_mps': requested['requested_speed_mps'],
                    'ego': body(ego),
                    'observed_road_id': None if wp is None else wp.road_id,
                    'observed_lane_id': None if wp is None else wp.lane_id,
                    'official_placement_verified': False,
                    'police_direction_verified': False,
                    'observed_device_obedience': None, 'legal_verdict': None}
                actors.write(json.dumps(row, allow_nan=False) + '\n')
                pipeline.capture(frame, time_s, extra={'c10389_device': row})
                for name, width, height, _, _, _ in specs:
                    image = queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Native/video frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                videos.write(json.dumps({'video_frame': i, 'native_frame': frame,
                                         'time_s': time_s}) + '\n')
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if pipeline is not None:
            try:
                pipeline.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('FFV1 encoder failed')
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
        write_new(output / 'native-capture-report.json', {
            'case_id': checked['case_id'], 'candidate_id': checked['candidate_id'],
            'config_sha256': sha(bundle / 'config.json'),
            'requested_frames': FRAMES,
            'observed_frames': frames, 'restoration': restored,
            'error': error, 'accepted': False,
            'stop_landmark_verified': landmark_verified,
            'official_placement_verified': False,
            'police_direction_verified': False,
            'legal_verdict': None, 'delivery_ready': False})
    if error:
        raise RuntimeError('C10389 Native attempt failed; see capture report')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--bundle', type=Path, default=Path.cwd())
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.bundle)))
    else:
        if args.output_dir is None:
            raise ValueError('Original Native output directory required')
        capture(args.bundle, args.output_dir, args.host, args.port)
