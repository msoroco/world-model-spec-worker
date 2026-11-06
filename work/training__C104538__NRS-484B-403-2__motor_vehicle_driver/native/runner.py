"""CPU preflight and Native map readback for proposed signed U-turn capture.

This module does not infer a physical sign or completed movement from the
authored OpenDRIVE. A later GPU operator must save original pixels and pose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import traceback

from cameras import PROFILE, RATE_HZ, camera_plan
from controller import PathController
from engineering import parameters
from geometry import check as geometry_check, open_drive

ROOT = Path(__file__).resolve().parent


def frame_map_row(index, frame, time_s):
    if type(index) is not int or index < 0 or type(frame) is not int or frame < 0:
        raise ValueError('Invalid source frame identity')
    if isinstance(time_s, bool) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
        raise ValueError('Invalid source time')
    return {'video_frame': index, 'native_frame': frame, 'carla_frame': frame, 'time_s': time_s}


def check(case_suffix, candidate_id):
    geometry = geometry_check()
    engineering = parameters(case_suffix, candidate_id)
    cameras = camera_plan(candidate_id)
    if len(cameras) != 4 or len({c['name'] for c in cameras}) != 4:
        raise ValueError('Four distinct original camera streams required')
    if (cameras[0]['width'], cameras[0]['height']) != (1920, 1080):
        raise ValueError('Overview resolution changed')
    if cameras[2]['xyz_m'] != engineering['sign_camera_xyz_m']:
        raise ValueError('Sign camera differs from candidate engineering')
    if engineering['rate_hz'] != RATE_HZ or engineering['duration_s'] != 24:
        raise ValueError('Native timebase differs from measured contract')
    PathController(engineering['native_route_xy_m'], 2.8, 35,
                   target_speed_mps=engineering['target_speed_mps'],
                   lookahead_m=engineering['lookahead_m'])
    return {'case_suffix': case_suffix, 'candidate_id': candidate_id,
            'camera_profile': PROFILE, 'camera_views': cameras,
            'native_route_points': len(engineering['native_route_xy_m']),
            'authored_geometry': geometry, 'map_readback_pending': True,
            'physical_sign_review_pending': True, 'native_capture_pending': True,
            'selected': False, 'native_imported': False}


def _direction(wp):
    v = wp.transform.get_forward_vector()
    length = math.hypot(v.x, v.y)
    if length < .9:
        raise RuntimeError('Native lane has no horizontal direction')
    return [v.x / length, v.y / length]


def map_survey(carla, mapping):
    """Validate live map readback before any physical claim or recording.

    The signal ID/type is emitted as observed metadata. Official legal sign
    meaning and original-pixel visibility require separate human review.
    """
    requests = {
        'signed_approach': (-35, 4, -1, [1, 0]),
        'signed_region': (-8, 4, -1, [1, 0]),
        'opposing_exit': (-8, -4, 1, [-1, 0]),
    }
    rows = {}
    for name, (x, y, lane_id, expected) in requests.items():
        wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=.2),
                                  project_to_road=False, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != lane_id:
            raise RuntimeError('Native lane readback failed: ' + name)
        direction = _direction(wp)
        if sum(a*b for a, b in zip(direction, expected)) < .98:
            raise RuntimeError('Native lane direction failed: ' + name)
        if not 7.8 <= wp.lane_width <= 8.2:
            raise RuntimeError('Native lane width failed: ' + name)
        rows[name] = {'road_id': wp.road_id, 'lane_id': wp.lane_id,
                      'native_xy_m': [wp.transform.location.x, wp.transform.location.y],
                      'native_z_m': wp.transform.location.z,
                      'direction_native_xy': direction, 'lane_width_m': wp.lane_width}
    landmarks = []
    for landmark in mapping.get_all_landmarks():
        if str(landmark.id) == '4032':
            landmarks.append({'id': str(landmark.id), 'type': str(landmark.type),
                              'road_id': int(landmark.road_id), 's_m': float(landmark.s)})
    if len(landmarks) != 1 or landmarks[0]['road_id'] != 1 or abs(landmarks[0]['s_m'] - 72) > .5:
        raise RuntimeError('Authored prohibition cue absent from Native landmark readback')
    return {'lane_readback': rows, 'landmark_readback': landmarks,
            'authored_opendrive_bytes': len(open_drive().encode()),
            'official_sign_status': 'unreviewed',
            'original_pixel_visibility': 'unreviewed',
            'physical_movement_observed': False}


def _camera_transform(carla, spec):
    x, y, z = spec['xyz_m']
    if spec['attachment'] == 'world':
        yaw = math.degrees(math.atan2(-y, -x))
        pitch = math.degrees(math.atan2(-z, math.hypot(x, y)))
    else:
        yaw, pitch = 0, spec['pitch_deg']
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def _body_xy(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    body = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
    if len(body) != 4:
        raise RuntimeError('Native full-body footprint unavailable')
    return [list(p) for p in body]


def _write_json_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def execute(case_suffix, candidate_id, output_dir, host, port):
    """Capture unaccepted original sources on an exclusively owned CARLA world.

    This does not run saved finalization: sign applicability and pixel labels
    must be reviewed from the retained original cameras first.
    """
    import carla
    import numpy as np
    runtime_package = Path(__file__).resolve().parents[3] / 'runtime' / 'pipeline' / 'scenario_pipeline'
    if runtime_package.is_dir():
        sys.path.insert(0, str(runtime_package))
    from worker_exchange.world_restore import snapshot, restore

    preflight = check(case_suffix, candidate_id)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    prior = client.get_world()
    if saved['settings'].synchronous_mode or [actor for actor in prior.get_actors()
            if actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))]:
        raise RuntimeError('Requires exclusive idle asynchronous CARLA world')
    actors, encoders, encoder_logs, camera_queues = [], {}, {}, {}
    changed, restored, error, frames = False, None, None, 0
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
        survey = map_survey(carla, mapping)
        native_xml = mapping.to_opendrive()
        survey['native_map_sha256'] = hashlib.sha256(native_xml.encode()).hexdigest()
        _write_json_new(output / 'road_geometry.json', survey)
        engineering = parameters(case_suffix, candidate_id)
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'c104538_4032_ego')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=-50, y=4, z=.5), carla.Rotation(yaw=0)))
        actors.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(40):
            world.tick()
        if not all(0 < y < 8 for _, y in _body_xy(ego)):
            raise RuntimeError('Native initial full body is outside signed approach lane')
        wheels = ego.get_physics_control().wheels
        if len(wheels) != 4:
            raise RuntimeError('Native wheel geometry unavailable')
        wheelbase = (max(w.position.x for w in wheels) - min(w.position.x for w in wheels)) / 100
        max_steer = max(w.max_steer_angle for w in wheels)
        controller = PathController(engineering['native_route_xy_m'], wheelbase, max_steer,
                                    target_speed_mps=engineering['target_speed_mps'],
                                    lookahead_m=engineering['lookahead_m'])
        _write_json_new(output / 'native-construction-context.json', {
            'case_suffix': case_suffix, 'candidate_id': candidate_id,
            'vehicle_blueprint': ego.type_id, 'wheelbase_m': wheelbase,
            'max_steer_deg': max_steer, 'native_route_points': len(controller.route),
            'camera_profile': preflight['camera_profile'],
            'requested_movement_observed': False, 'selected': False})
        for spec in camera_plan(candidate_id):
            camera_blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']),
                               ('image_size_y', spec['height']), ('fov', spec['fov_deg']),
                               ('sensor_tick', 0)):
                camera_blueprint.set_attribute(key, str(value))
            camera = world.spawn_actor(camera_blueprint, _camera_transform(carla, spec),
                attach_to=ego if spec['attachment'] == 'ego' else None)
            actors.append(camera)
            camera_queues[spec['name']] = queue.Queue()
            camera.listen(camera_queues[spec['name']].put)
            log = (output / (spec['name'] + '.encoder.log')).open('x')
            encoder_logs[spec['name']] = log
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s',
                f"{spec['width']}x{spec['height']}", '-r', '20', '-i', 'pipe:0',
                '-an', '-c:v', 'ffv1', '-level', '1', str(output / (spec['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=log)
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native_samples.jsonl').open('x') as native_file, \
             (output / 'video_frames.jsonl').open('x') as frame_file:
            for index in range(480):
                before = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                command = controller.step(position_xy_m=(before.location.x, before.location.y),
                    yaw_rad=math.radians(before.rotation.yaw), speed_mps=speed, dt_s=.05)
                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],
                    brake=command['brake'], steer=command['steer'],
                    hand_brake=command['hand_brake']))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                lane = mapping.get_waypoint(pose.location, project_to_road=False,
                                            lane_type=carla.LaneType.Driving)
                if lane is None:
                    raise RuntimeError('Original Native lane identity missing')
                body = _body_xy(ego)
                forward = pose.get_forward_vector()
                forward_length = math.hypot(forward.x, forward.y)
                if forward_length < .9:
                    raise RuntimeError('Original Native horizontal heading missing')
                sample = {'native_frame': frame, 'time_s': time_s,
                    'native_center_xy_m': [sum(p[0] for p in body)/4,
                                           sum(p[1] for p in body)/4],
                    'native_forward_xy': [forward.x/forward_length,
                                          forward.y/forward_length],
                    'native_heading_deg': pose.rotation.yaw,
                    'native_body_xy_m': body,
                    'native_road_id': lane.road_id, 'native_lane_id': lane.lane_id,
                    'speed_mps': speed, 'controller_request': command}
                native_file.write(json.dumps(sample, allow_nan=False) + '\n')
                for spec in camera_plan(candidate_id):
                    image = camera_queues[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera/Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                frame_file.write(json.dumps(frame_map_row(index, frame, time_s)) + '\n')
                frames += 1
        if frames != 480:
            raise RuntimeError('Original capture frame count incomplete')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        encoder_exit_codes = {}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                encoder_exit_codes[name] = encoder.wait(timeout=180)
                if encoder_exit_codes[name] != 0:
                    raise RuntimeError('Lossless camera encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for actor in reversed(actors):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        _write_json_new(output / 'native-capture-report.json', {
            'case_suffix': case_suffix, 'candidate_id': candidate_id,
            'frames': frames, 'expected_frames': 480,
            'encoder_exit_codes': encoder_exit_codes, 'restoration': restored,
            'error': error, 'accepted': False,
            'original_pixel_review': 'pending', 'official_sign_review': 'pending',
            'saved_processing': 'pending', 'selected': False})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json: ' + str(error))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case', choices=('witness_1', 'witness_2'))
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'))
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config_path = ROOT / 'config.json'
    config = json.loads(config_path.read_text()) if config_path.is_file() else {}
    case_suffix = args.case or config.get('case_suffix')
    candidate_id = args.candidate or config.get('candidate_id')
    if not case_suffix or not candidate_id:
        parser.error('Supply --case and --candidate or a materialized config.json')
    if args.check:
        print(json.dumps(check(case_suffix, candidate_id), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Supply output directory, host and port for an owned Native attempt')
        execute(case_suffix, candidate_id, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
