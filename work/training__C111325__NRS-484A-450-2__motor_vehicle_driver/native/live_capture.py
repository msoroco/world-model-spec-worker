"""Original Native acquisition for the near-side crosswalk stop comparison.

Run only with an idle local CARLA server. The resulting attempt is a source
recording for later finalization; a requested stop is never a measured stop.
"""
import argparse
import hashlib
import json
import math
import queue
import subprocess
import traceback
from pathlib import Path

from runner import ASSIGNMENT, CAMERAS, FRAMES, RATE_HZ, capture_row, check

HERE = Path(__file__).resolve().parent
START_Y = -50.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def requested_speed(index, case, front_y):
    """Hold a requested stop with margin before the crosswalk's near edge.

    The case target remains a request. Actual body position and speed are
    measured after each tick; finalization can reject a failed maneuver.
    """
    if not 0 <= index < FRAMES or case not in (ASSIGNMENT + '__probe_1',
                                              ASSIGNMENT + '__probe_2'):
        raise ValueError('Exact frame or case differs')
    if case.endswith('probe_1') and 100 <= index < 180:
        if front_y >= -12.5:
            raise RuntimeError('Stop approach passed the pre-crosswalk margin')
        return 0.0
    return 4.0


def command(carla, actor, target_speed, target_x):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    lateral = target_x - pose.location.x
    yaw_error = 90.0 - pose.rotation.yaw
    yaw_error = (yaw_error + 180.0) % 360.0 - 180.0
    steer = max(-.6, min(.6, .05 * lateral + .015 * yaw_error))
    throttle = max(0.0, min(.8, .2 + .25 * (target_speed - speed))) if target_speed else 0.0
    brake = max(0.0, min(1.0, .35 * (speed - target_speed)))
    if target_speed == 0:
        brake = 1.0
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer)


def acquire(bundle, output, host, port):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    config = json.loads((bundle / 'config.json').read_text())
    check(config)
    if output != bundle and output.exists():
        raise ValueError('Native output must be a fresh directory')
    if (bundle / 'authored-road.xodr').is_file():
        road = bundle / 'authored-road.xodr'
    else:
        road = bundle / 'road.xodr'
    if not road.is_file():
        raise ValueError('Authored road missing from bundle')
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
            a.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for a in original_world.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    output.mkdir(parents=True, exist_ok=output == bundle)
    if output != bundle:
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
        spawn = mapping.get_waypoint(carla.Location(x=1.75, y=START_Y, z=1.0),
                                     project_to_road=False,
                                     lane_type=carla.LaneType.Driving)
        if spawn is None or spawn.road_id != 1 or spawn.lane_id != -1:
            raise RuntimeError('Signed subject approach lane not observed')
        library = world.get_blueprint_library()
        blueprint = library.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name', 'c111325_ego')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=1.75, y=START_Y, z=2.0), carla.Rotation(yaw=90)))
        owned.append(ego)
        for _ in range(30):
            world.tick()
        cameras = (
            ('overview', 1920, 1080, carla.Transform(carla.Location(x=35, y=-12, z=25),
                                                     carla.Rotation(yaw=180, pitch=-25)), None),
            ('approach', 1280, 720, carla.Transform(carla.Location(x=15, y=-22, z=8),
                                                    carla.Rotation(yaw=180, pitch=-15)), None),
            ('reference_corner', 1280, 720,
             carla.Transform(carla.Location(x=-14, y=-7, z=9),
                             carla.Rotation(yaw=-45, pitch=-15)), None),
            ('driver_reference', 1280, 720,
             carla.Transform(carla.Location(x=1, y=0, z=1.4)), ego))
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
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=True, required_observations=())
        start_time = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native_samples.jsonl').open('x') as rows, \
                FrameMap(output / 'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                pose = ego.get_transform()
                front_y = max(v.y for v in ego.bounding_box.get_world_vertices(pose))
                target = requested_speed(index, config['case_id'], front_y)
                ego.apply_control(command(carla, ego, target, 1.75))
                frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start_time
                waypoint = mapping.get_waypoint(ego.get_transform().location,
                                                project_to_road=False,
                                                lane_type=carla.LaneType.Driving)
                observation = capture_row(index, frame, elapsed, ego, waypoint)
                capture.capture(frame, elapsed, extra={'c111325_stop': observation})
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
            'world_restore': restore_status,
            'physical_scene_reviewed': False,
            'legal_verdict_claimed': False}, indent=2) + '\n')
    if error is not None or frame_count != FRAMES:
        raise RuntimeError('Native acquisition incomplete: ' + str(error))
    originals = [json.loads(line) for line in (output / 'native_samples.jsonl').read_text().splitlines()]
    (output / 'stop_history.jsonl').write_text(''.join(json.dumps({
        'frame': row['native_frame'], 'time_s': row['time_s'],
        'body_vertices_m': row['body_vertices_m']}, allow_nan=False) + '\n'
        for row in originals))
    (output / 'crosswalk_geometry.json').write_text(json.dumps({
        'intersection_polygon_xy_m': [[-7, -7], [7, -7], [7, 7], [-7, 7]],
        'crosswalk_near_edge_y_m': -11,
        'road_sha256': sha(output / 'road.xodr'),
        'source': 'authored OpenDRIVE junction extent; physical review pending',
    }, indent=2) + '\n')
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
