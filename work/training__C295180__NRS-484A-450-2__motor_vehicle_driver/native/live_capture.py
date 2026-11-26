"""Prospective original CARLA capture for the C295180 stop-line comparison.

The controller requests motion only. Saved original body, speed, road and camera
sources decide whether a stop actually preceded the operative marked line.
"""
import argparse
import hashlib
import json
import math
import queue
import subprocess
import traceback
from pathlib import Path

from road_source import inspect as inspect_road
from stop_line_request import CASES, FRAMES, RATE_HZ


CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
ROAD = Path(__file__).resolve().parent / 'authored-road.xodr'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def requested_speed(index, case):
    if not 0 <= index < FRAMES or case not in CASES.values():
        raise ValueError('Exact frame/case identity differs')
    if case == CASES['full_stop'] and 112 <= index < 181:
        return 0.0
    if case == CASES['rolling'] and 112 <= index < 181:
        return 2.0
    return 8.0


def control(carla, ego, target_speed):
    velocity = ego.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    pose = ego.get_transform()
    yaw_error = ((90 - pose.rotation.yaw + 180) % 360) - 180
    steer = max(-.6, min(.6, .05 * (1.75 - pose.location.x) + .015 * yaw_error))
    throttle = max(0, min(.8, .2 + .25 * (target_speed - speed))) if target_speed else 0
    brake = 1.0 if target_speed == 0 else max(0, min(1, .35 * (speed - target_speed)))
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer)


def capture(case_id, output, host='127.0.0.1', port=2000):
    if case_id not in CASES.values():
        raise ValueError('Exact selected case differs')
    road_info = inspect_road(ROAD)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Native output must be fresh')
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved_world = snapshot(client)
    original = client.get_world()
    if saved_world['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in original.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    output.mkdir(parents=True)
    (output / 'road.xodr').write_bytes(ROAD.read_bytes())
    (output / 'config.json').write_text(json.dumps({
        'case_id': case_id, 'selected_case_id': case_id,
        'law_id': 'NRS-484A-450-2', 'cell_id': 'C295180',
        'actor': 'motor_vehicle_driver', 'rate_hz': RATE_HZ,
        'duration_s': 30, 'cameras': [dict(name=n, width=w, height=h, fps=RATE_HZ)
                                  for n, w, h in CAMERAS],
        'physical_verified': False, 'legal_verdict': None}, indent=2) + '\n')
    owned, encoders, encoder_logs, cameras = [], {}, {}, {}
    pipeline = None
    changed = False
    failure = None
    frame_count = 0
    restore_status = None
    try:
        world = client.generate_opendrive_world(ROAD.read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        waypoint = world.get_map().get_waypoint(carla.Location(x=1.75, y=-61, z=1),
            project_to_road=False, lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != -1:
            raise RuntimeError('Subject signed approach lane readback differs')
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name', 'c295180_ego')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=1.75, y=-61, z=2), carla.Rotation(yaw=90)))
        owned.append(ego)
        for _ in range(30):
            world.tick()
        placements = (
            ('overview', carla.Transform(carla.Location(x=30, y=-12, z=25),
                                         carla.Rotation(yaw=180, pitch=-25)), None),
            ('approach', carla.Transform(carla.Location(x=15, y=-22, z=8),
                                         carla.Rotation(yaw=180, pitch=-15)), None),
            ('reference_corner', carla.Transform(carla.Location(x=-12, y=-7, z=9),
                                                 carla.Rotation(yaw=-45, pitch=-15)), None),
            ('driver_reference', carla.Transform(carla.Location(x=1, y=0, z=1.4)), ego))
        for (name, width, height), (_, transform, attached) in zip(CAMERAS, placements):
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                camera_bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(camera_bp, transform, attach_to=attached)
            owned.append(sensor)
            cameras[name] = queue.Queue()
            encoder_logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', str(RATE_HZ), '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=encoder_logs[name])
            sensor.listen(cameras[name].put)
        pipeline = PipelineCapture(client, ego, output, case_id,
            visibility=False, required_observations=())
        start_time = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native_samples.jsonl').open('x') as rows, \
                FrameMap(output / 'video_frames.jsonl') as mapping:
            for index in range(FRAMES):
                ego.apply_control(control(carla, ego, requested_speed(index, case_id)))
                frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start_time
                pose = ego.get_transform()
                body = ego.bounding_box.get_world_vertices(pose)
                speed_vector = ego.get_velocity()
                speed = math.sqrt(speed_vector.x**2 + speed_vector.y**2 + speed_vector.z**2)
                row = {'case_id': case_id, 'frame': index, 'native_frame': frame,
                       'time_s': elapsed, 'ego': {
                           'center_x_m': pose.location.y + 11,
                           'front_x_m': max(vertex.y for vertex in body) + 11,
                           'speed_mps': speed},
                       'source_kind': 'original_native_readback'}
                rows.write(json.dumps(row, allow_nan=False) + '\n')
                pipeline.capture(frame, elapsed, extra={'c295180_stop_line': row})
                for name, width, height in CAMERAS:
                    image = cameras[name].get(timeout=30)
                    while image.frame < frame:
                        image = cameras[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Camera/Native frame identity differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                mapping.append(frame, elapsed)
                frame_count += 1
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error),
                   'traceback': traceback.format_exc()}
    finally:
        if pipeline is not None:
            try:
                pipeline.close(confirmed=failure is None)
            except BaseException as error:
                failure = failure or {'capture_close_error': str(error)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Camera encoder failed: ' + name)
            except BaseException as error:
                failure = failure or {'encoder_error': str(error)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                actor.destroy()
            except BaseException:
                pass
        if changed:
            try:
                restore_status = restore(client, saved_world)
            except BaseException as error:
                failure = failure or {'world_restore_error': str(error)}
        (output / 'native-acquisition.json').write_text(json.dumps({
            'case_id': case_id, 'frames': frame_count,
            'road_source_sha256': sha(ROAD), 'error': failure,
            'world_restore': restore_status, 'physical_scene_reviewed': False,
            'legal_verdict_claimed': False}, indent=2) + '\n')
    if failure is not None or frame_count != FRAMES:
        raise RuntimeError('Native acquisition incomplete: ' + str(failure))
    (output / 'stop_reference.json').write_text(json.dumps({
        'stop_sign_present': True, 'governs_ego_lane': True,
        'near_crosswalk_present': False, 'marked_stop_line_x_m': 0,
        'intersection_near_boundary_x_m': 4,
        'source_kind': 'original_native_readback',
        'authored_road_sha256': sha(ROAD), 'road_review': road_info}, indent=2) + '\n')
    names = ('native_samples.jsonl', 'video_frames.jsonl', 'stop_reference.json')
    (output / 'source-seal.json').write_text(json.dumps({
        'format': 'c295180-saved-source-seal-v1', 'case_id': case_id,
        'source_sha256': {name: sha(output / name) for name in names}}, indent=2) + '\n')
    return {'case_id': case_id, 'frames': frame_count, 'output': str(output),
            'physical_scene_reviewed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--output')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        print(json.dumps({'road': inspect_road(ROAD),
                          'full_stop_zero_requests': sum(
                              requested_speed(i, CASES['full_stop']) == 0
                              for i in range(FRAMES)),
                          'rolling_zero_requests': sum(
                              requested_speed(i, CASES['rolling']) == 0
                              for i in range(FRAMES)),
                          'simulation_started': False}, sort_keys=True))
    else:
        if not args.case or not args.output:
            parser.error('--case and --output are required for capture')
        print(json.dumps(capture(args.case, args.output, args.host, args.port)))
