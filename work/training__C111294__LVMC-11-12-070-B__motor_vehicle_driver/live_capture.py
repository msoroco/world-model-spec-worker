"""Original two-actor Native acquisition; execute only on an idle local CARLA server."""
import argparse
import hashlib
import json
import math
import os
import queue
import subprocess
import sys
import traceback
from pathlib import Path

from runner import ASSIGNMENT, CAMERAS, FRAMES, RATE_HZ, capture_row, check, request

HERE = Path(__file__).resolve().parent
ROOT = next((path for path in (HERE, *HERE.parents)
             if (path / 'runtime/SOURCE-MANIFEST.json').is_file()), None)
if ROOT is None:
    raise RuntimeError('Current repository runtime not found')
THROUGH_START_AUTHORED_Y_M = 65.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(carla, actor, target_speed, target_xy, target_yaw):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    heading = math.radians(target_yaw)
    dx = target_xy[0] - pose.location.x
    dy = target_xy[1] - pose.location.y
    lateral = -math.sin(heading) * dx + math.cos(heading) * dy
    yaw_error = (target_yaw - pose.rotation.yaw + 180) % 360 - 180
    steer = max(-.6, min(.6, .05 * lateral + .015 * yaw_error))
    throttle = max(0.0, min(.8, .2 + .25 * (target_speed - speed))) if target_speed else 0.0
    brake = 1.0 if target_speed == 0 else max(0.0, min(1.0, .35 * (speed - target_speed)))
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer)


def acquire(bundle, output, host='127.0.0.1', port=2000):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    config = json.loads((bundle / 'config.json').read_text())
    check(config)
    if output.exists():
        raise ValueError('Native output must be a fresh directory')
    if not output.is_relative_to(ROOT / '.runtime-work'):
        raise ValueError('Native recording output must stay under .runtime-work')
    road = bundle / 'authored-road.xodr'
    if not road.is_file():
        road = bundle / 'road.xodr'
    if not road.is_file():
        raise ValueError('Authored road missing from bundle')
    runtime_output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if not runtime_output.is_relative_to(ROOT / '.runtime-work'):
        raise ValueError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import')
    sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
    sys.path.insert(0, str(ROOT / 'runtime/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    original_world = client.get_world()
    if saved['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in original_world.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    output.mkdir(parents=True)
    (output / 'config.json').write_bytes((bundle / 'config.json').read_bytes())
    (output / 'road.xodr').write_bytes(road.read_bytes())
    owned, encoders, encoder_logs, camera_queues = [], {}, {}, {}
    capture = None
    changed = False
    error = None
    frame_count = 0
    restore_status = None
    try:
        world = client.generate_opendrive_world(
            road.read_text(), carla.OpendriveGenerationParameters(
                vertex_distance=.25, max_road_length=50, wall_height=0,
                additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        # At the 8 m/s request, 142 frames traverse 56.8 m; the 65 m
        # approach leaves a nominal 8.2 m margin before the hold request.
        start = {'through': (-1.75, -THROUGH_START_AUTHORED_Y_M, 1.0, 90, 4, 1),
                 'entrant': (-12.0, 1.75, 1.0, 0, 3, -1)}
        for name, (x, y, z, _, road_id, lane_id) in start.items():
            waypoint = mapping.get_waypoint(carla.Location(x=x, y=y, z=z),
                                            project_to_road=False,
                                            lane_type=carla.LaneType.Driving)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (road_id, lane_id):
                raise RuntimeError('Signed ' + name + ' approach lane not observed')
        library = world.get_blueprint_library()
        actors = {}
        for name, (x, y, z, yaw, _, _) in start.items():
            blueprint = library.find('vehicle.tesla.model3')
            blueprint.set_attribute('role_name', 'c111294_' + name)
            actors[name] = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(x=x, y=y, z=z + 1.0), carla.Rotation(yaw=yaw)))
            owned.append(actors[name])
        for _ in range(30):
            world.tick()
        cameras = (
            ('overview', 1920, 1080, carla.Transform(
                carla.Location(x=30, y=15, z=25), carla.Rotation(yaw=-150, pitch=-25)), None),
            ('approach', 1280, 720, carla.Transform(
                carla.Location(x=14, y=-24, z=9), carla.Rotation(yaw=150, pitch=-15)), None),
            ('reference_corner', 1280, 720, carla.Transform(
                carla.Location(x=-15, y=12, z=9), carla.Rotation(yaw=-25, pitch=-15)), None),
            ('driver_reference', 1280, 720, carla.Transform(
                carla.Location(x=1, y=0, z=1.4)), actors['through']))
        if tuple((name, width, height) for name, width, height, _, _ in cameras) != CAMERAS:
            raise RuntimeError('Four-camera source profile changed')
        for name, width, height, transform, attached in cameras:
            camera_bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                camera_bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(camera_bp, transform, attach_to=attached)
            owned.append(sensor)
            camera_queues[name] = queue.Queue()
            encoder_logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', str(RATE_HZ), '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=encoder_logs[name])
            sensor.listen(camera_queues[name].put)
        capture = PipelineCapture(client, actors['through'], output, config['case_id'],
                                  visibility=True, required_observations=())
        start_time = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native_samples.jsonl').open('x') as rows, \
                FrameMap(output / 'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                targets = request(index, config['case_id'])
                actors['through'].apply_control(command(
                    carla, actors['through'], targets['through_target_speed_mps'],
                    (-1.75, -30), 90))
                actors['entrant'].apply_control(command(
                    carla, actors['entrant'], targets['entrant_target_speed_mps'],
                    (30, 1.75), 0))
                frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start_time
                waypoints = {name: mapping.get_waypoint(
                    actor.get_transform().location, project_to_road=False,
                    lane_type=carla.LaneType.Driving)
                    for name, actor in actors.items()}
                observation = capture_row(index, frame, elapsed, actors['through'],
                                          actors['entrant'], waypoints['through'],
                                          waypoints['entrant'])
                capture.capture(frame, elapsed, extra={'c111294_yield': observation})
                rows.write(json.dumps(observation, allow_nan=False) + '\n')
                for name, width, height, _, _ in cameras:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Camera and Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.append(frame, elapsed)
                frame_count += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Camera encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                actor.destroy()
            except BaseException:
                pass
        if changed:
            try:
                restore_status = restore(client, saved)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        (output / 'native-acquisition.json').write_text(json.dumps({
            'case_id': config['case_id'], 'frames': frame_count,
            'road_source_sha256': sha(road), 'error': error,
            'world_restore': restore_status, 'physical_scene_reviewed': False,
            'legal_verdict_claimed': False}, indent=2) + '\n')
    if error is not None or frame_count != FRAMES:
        raise RuntimeError('Native acquisition incomplete: ' + str(error))
    (output / 'diagnostic-source-manifest.json').write_text(json.dumps({
        'case_id': config['case_id'], 'source_kind': 'native_observation',
        'sha256': {name: sha(output / name) for name in
                   ('road.xodr', 'native_samples.jsonl')}}, indent=2) + '\n')
    return {'case_id': config['case_id'], 'frames': frame_count,
            'output': str(output), 'physical_scene_reviewed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    print(json.dumps(acquire(args.bundle, args.output, args.host, args.port)))
