"""Exact C111331 request preflight and later owned Native capture.

The CPU path reads only the materialized bundle. The capture path records
observations separately from requested positions and signal states.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C111331__NRS-484B-307-6a__motor_vehicle_driver'
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check():
    config = json.loads((HERE / 'config.json').read_text())
    requests = rows(HERE / 'native-requests.jsonl')
    case = config['case_suffix']
    candidate = config['candidate_id']
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown exact case or candidate')
    if config['case_id'] != ASSIGNMENT + '__' + case or config['cell_id'] != 'C111331' or config['law_id'] != 'NRS-484B-307-6a':
        raise ValueError('Frozen case identity differs')
    if config['actor'] != 'motor_vehicle_driver' or config['rate_hz'] != 20 or config['duration_s'] != 24:
        raise ValueError('Frozen actor or capture profile differs')
    if config['frozen_cell'] != {'layout': 'intersection', 'maneuver': 'travel', 'control': 'traffic_light'}:
        raise ValueError('Frozen scenario cell differs')
    if config['road_sha256'] != sha(HERE / 'road.xodr') or config['native_requests_sha256'] != sha(HERE / 'native-requests.jsonl'):
        raise ValueError('Exact road or request hash differs')
    root = ET.parse(HERE / 'road.xodr').getroot()
    if not root.findall('.//junction') or not any(s.get('id') == '601' for s in root.findall('.//signal')):
        raise ValueError('Requested intersection signal is absent')
    if len(requests) != 480 or any(r['frame'] != i or r['time_s'] != round(i / 20, 4) for i, r in enumerate(requests)):
        raise ValueError('Request frame/time join differs')
    red = config['knobs'][case + '_red_frame']
    entry = None
    for i, r in enumerate(requests):
        expected = 'green' if i < 150 else 'yellow' if i < red else 'red'
        if r['source_kind'] != 'authored_cpu_request' or r['signal_phase_requested'] != expected or r['signal_red_start_requested_frame'] != red:
            raise ValueError('Requested signal phase differs')
        if r['actual_signal_phase_observed'] is not None or r['actual_intersection_entry_observed'] is not None:
            raise ValueError('Request was promoted to observation')
        center = r['native_center_xy_m']
        body = r['native_body_xy_m']
        if len(body) != 4 or center[0] != 1.75 or abs(sum(p[0] for p in body) / 4 - center[0]) > 1e-5 or abs(sum(p[1] for p in body) / 4 - center[1]) > 1e-5:
            raise ValueError('Requested body and center differ')
        if i and abs((requests[i - 1]['native_center_xy_m'][1] - center[1]) - config['knobs']['speed_m_per_frame']) > 1e-4:
            raise ValueError('Requested motion cadence differs')
        if entry is None and -min(p[1] for p in body) >= -7:
            entry = i
    metrics = config['metrics']
    if entry != metrics['requested_full_body_entry_frame'] or requests[entry]['signal_phase_requested'] != metrics['requested_phase_at_entry']:
        raise ValueError('Entry and signal metric differ')
    if metrics['requested_phase_at_entry'] != ('yellow' if case == 'reference' else 'red'):
        raise ValueError('Controlled phase differs')
    trigger = config['measured_trigger']
    value = metrics[trigger['metric']]
    if trigger['measured'] != value or not {'equals': value == trigger['target'], 'at_least': value >= trigger['target'] if isinstance(value, (int, float)) else False, 'at_most': value <= trigger['target'] if isinstance(value, (int, float)) else False}[trigger['operator']]:
        raise ValueError('Measured candidate trigger differs')
    if not config['no_native_or_original_observation_claimed']:
        raise ValueError('Physical evidence claimed by CPU request')
    return {'passed': True, 'case': case, 'candidate': candidate, 'request_rows': len(requests),
            'requested_entry_frame': entry, 'requested_phase_at_entry': metrics['requested_phase_at_entry'],
            'carla_imported': False, 'physical_success_claimed': False}


def _body_xy(actor):
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in actor.bounding_box.get_world_vertices(actor.get_transform())})
    if len(points) != 4:
        raise RuntimeError('Native body footprint is not four corners')
    return [list(p) for p in points]


def saved_capture_rows(sample, video_frame):
    """Build the three synchronized saved sources from one observed tick."""
    if video_frame != sample['request_index'] or len(sample['native_body_xy_m']) != 4:
        raise ValueError('Observed capture frame or body differs')
    sample = dict(sample, source_kind='original_native_observation')
    x, y = sample['native_center_xy_m']
    trace = {'frame': sample['native_frame'], 'time_s': sample['time_s'],
             'position': {'x': x, 'y': y, 'z': sample['native_z_m']},
             'position_m': [x, y, sample['native_z_m']],
             'heading_deg': sample['native_yaw_deg'], 'speed_mps': sample['speed_mps']}
    video = {'video_frame': video_frame, 'native_frame': sample['native_frame'],
             'time_s': sample['time_s']}
    return sample, trace, video


def signal_camera_plan(config):
    camera_xy = config['camera_plan']['authored_xy_m']
    head_xy = config['camera_plan']['signal_head_authored_xy_m']
    dx, dy = head_xy[0] - camera_xy[0], head_xy[1] - camera_xy[1]
    if math.hypot(dx, dy) < 1 or not 1 <= config['camera_plan']['horizontal_fov_deg'] <= 120:
        raise ValueError('Authored signal camera geometry differs')
    return {'x': camera_xy[0], 'y': camera_xy[1],
            'yaw_deg': math.degrees(math.atan2(dy, dx)),
            'horizontal_fov_deg': config['camera_plan']['horizontal_fov_deg']}


def execute(output, host, port):
    """Capture an original 480-frame attempt on an explicitly owned idle server.

    The resulting sources still need saved processing, pixel review and an
    independent audit before any candidate can be selected.
    """
    import carla
    import numpy as np
    from worker_exchange.world_restore import snapshot, restore

    check()
    output = Path(output).resolve()
    if output != HERE or not (output / 'construction.json').is_file():
        raise ValueError('Capture requires the exact materialized bundle directory')
    config = json.loads((HERE / 'config.json').read_text())
    requested = rows(HERE / 'native-requests.jsonl')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old_world.get_actors()):
        raise RuntimeError('Requires an exclusive idle asynchronous Native world')
    owned = []
    camera_queue = queue.Queue()
    encoder = None
    encoder_log = None
    changed = False
    error = None
    restored = None
    count = 0
    try:
        world = client.generate_opendrive_world((HERE / 'road.xodr').read_text(), carla.OpendriveGenerationParameters(
            vertex_distance=.25, max_road_length=50, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True, enable_pedestrian_navigation=False))
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
        first = requested[0]['native_center_xy_m']
        waypoint = mapping.get_waypoint(carla.Location(x=first[0], y=first[1], z=.2), project_to_road=False, lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 1:
            raise RuntimeError('Native imported approach lane survey differs')
        signals = list(world.get_actors().filter('traffic.traffic_light*'))
        if not signals:
            raise RuntimeError('OpenDRIVE signal did not instantiate a Native traffic light')
        head_xy = config['camera_plan']['signal_head_authored_xy_m']
        signal = min(signals, key=lambda a: math.dist((a.get_location().x, a.get_location().y), head_xy))
        if math.dist((signal.get_location().x, signal.get_location().y), head_xy) > 10:
            raise RuntimeError('Native signal location does not match authored approach')
        signal.freeze(True)
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'c111331_ego')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=first[0], y=first[1], z=.5), carla.Rotation(yaw=-90)))
        owned.append(ego)
        camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
        camera_bp.set_attribute('image_size_x', '1280')
        camera_bp.set_attribute('image_size_y', '720')
        camera = signal_camera_plan(config)
        camera_bp.set_attribute('fov', str(camera['horizontal_fov_deg']))
        camera_bp.set_attribute('sensor_tick', '0')
        sensor = world.spawn_actor(camera_bp, carla.Transform(
            carla.Location(x=camera['x'], y=camera['y'], z=3),
            carla.Rotation(pitch=8, yaw=camera['yaw_deg'])), attach_to=None)
        owned.append(sensor)
        sensor.listen(camera_queue.put)
        encoder_log = (output / 'signal_reference.encoder.log').open('x')
        encoder = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1280x720', '-r', '20', '-i', 'pipe:0',
            '-an', '-c:v', 'ffv1', '-level', '1', str(output / 'signal_reference.mkv')],
            stdin=subprocess.PIPE, stderr=encoder_log)
        with (output / 'native_samples.jsonl').open('x') as sample_file, \
                (output / 'video_frames.jsonl').open('x') as frame_file, \
                (output / 'trace.jsonl').open('x') as trace_file:
            start = world.get_snapshot().timestamp.elapsed_seconds
            for index, request in enumerate(requested):
                phase = request['signal_phase_requested']
                signal.set_state({'green': carla.TrafficLightState.Green, 'yellow': carla.TrafficLightState.Yellow,
                                  'red': carla.TrafficLightState.Red}[phase])
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.hypot(velocity.x, velocity.y)
                target = request['native_center_xy_m']
                lateral = target[0] - pose.location.x
                heading_error = ((-90 - pose.rotation.yaw + 180) % 360) - 180
                steer = max(-.35, min(.35, .08 * lateral + .012 * heading_error))
                target_speed = config['knobs']['speed_m_per_frame'] * 20
                throttle = max(0, min(.6, .15 * (target_speed - speed)))
                brake = max(0, min(.8, .2 * (speed - target_speed)))
                control = {'throttle': throttle, 'brake': brake, 'steer': steer}
                ego.apply_control(carla.VehicleControl(**control))
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                body = _body_xy(ego)
                native_sample = {'request_index': index, 'native_frame': frame, 'time_s': now,
                    'native_center_xy_m': [pose.location.x, pose.location.y], 'native_z_m': pose.location.z,
                    'native_body_xy_m': body,
                    'native_yaw_deg': pose.rotation.yaw, 'speed_mps': speed,
                    'requested_signal_phase': phase, 'observed_signal_state': str(signal.get_state()),
                    'signal_actor_id': signal.id, 'approach_road_id': waypoint.road_id,
                    'approach_lane_id': waypoint.lane_id, 'controller_request': control,
                    'body_entered_junction_observed': min(p[1] for p in body) <= 7.0}
                image = camera_queue.get(timeout=30)
                while image.frame < frame:
                    image = camera_queue.get(timeout=30)
                if image.frame != frame:
                    raise RuntimeError('Original camera and Native frame join failed')
                rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(720, 1280, 4)[:, :, :3][:, :, ::-1]
                encoder.stdin.write(rgb.tobytes())
                sample_row, trace_row, frame_row = saved_capture_rows(native_sample, index)
                sample_file.write(json.dumps(sample_row, allow_nan=False) + '\n')
                trace_file.write(json.dumps(trace_row, allow_nan=False) + '\n')
                frame_file.write(json.dumps(frame_row, allow_nan=False) + '\n')
                count += 1
        if count != 480:
            raise RuntimeError('Original capture frame count differs')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
    finally:
        if encoder is not None:
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180):
                    raise RuntimeError('Original lossless encoder failed')
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
        if encoder_log is not None:
            encoder_log.close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.'):
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        (output / 'native-execution-summary.json').write_text(json.dumps({
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'], 'frames_written': count,
            'error': error, 'world_restored': restored, 'acceptance_claimed': False}, indent=2, default=str) + '\n')
    if error:
        raise RuntimeError('Native capture failed; inspect native-execution-summary.json: ' + str(error))
    return {'frames_written': count, 'acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    print(json.dumps(check() if args.check else execute(args.output_dir, args.host, args.port), sort_keys=True))
