"""Prospective original CARLA capture; physical success is assessed after saving."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from cameras import check as check_cameras, plan as camera_plan
from controller import EngineeringKnobs, PathController
from geometry import APPROACH_M, RADIUS_M, check as check_geometry, open_drive, route
from measure_observed import CASE_PREFIX

HERE = Path(__file__).resolve().parent


def check(config: dict) -> dict:
    case = config.get('case_id')
    if case not in (CASE_PREFIX + 'a', CASE_PREFIX + 'b', CASE_PREFIX + 'c'):
        raise ValueError('Exact C42417 case differs')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != \
            ('NRS-484B-413-2', 'C42417', 'motor_vehicle_driver'):
        raise ValueError('Frozen assignment identity differs')
    if (config.get('rate_hz'), config.get('duration_s')) != (20, 30):
        raise ValueError('Full 600-frame window required')
    if (config.get('layout'), config.get('maneuver'), config.get('precipitation')) != \
            ('business_district', 'right_turn', 'rain'):
        raise ValueError('Fixed business district scene differs')
    expected = {'a':40,'b':20,'c':30.48}[case[-1]]
    if config.get('signal_distance_m') != expected:
        raise ValueError('Exact signal distance request differs')
    if config.get('controller_lookahead_base_m') not in (4.0, 2.5):
        raise ValueError('Undeclared controller lookahead candidate')
    return {'case_id': case, 'frames': 600, 'geometry': check_geometry(),
            'cameras': check_cameras(), 'signal_start_x_m': -expected,
            'simulation_started': False, 'selected_for_delivery': False,
            'physical_success_claimed': False}


def _new(path: Path, value: dict) -> None:
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def _speed(actor) -> float:
    v = actor.get_velocity()
    speed = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if not math.isfinite(speed):
        raise ValueError('Nonfinite original Native velocity')
    return speed


def _camera_pose(carla, spec):
    x, y, z = spec['xyz_m']
    if spec['attachment'] == 'world':
        target_x, target_y = -10.0, 3.0
        yaw = math.degrees(math.atan2(target_y - y, target_x - x))
        pitch = math.degrees(math.atan2(-z, math.hypot(target_x - x, target_y - y)))
    else:
        yaw, pitch = 0.0, spec['pitch_deg']
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def capture(config: dict, output_dir: Path, host: str, port: int) -> dict:
    """Write only new original sources; return a failure report after cleanup."""
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use a fresh materialized exact-case output directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old_world = client.get_world()
    if old_world.get_settings().synchronous_mode or [actor for actor in old_world.get_actors()
            if actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))]:
        raise RuntimeError('Exclusive idle asynchronous world ownership required')
    owned, encoders, logs, image_queues = [], {}, {}, {}
    pipeline = None
    world_changed = False
    frames = 0
    error = None
    restored = None
    try:
        map_text = open_drive()
        world = client.generate_opendrive_world(map_text,
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        world_changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.HardRainNoon)
        mapping = world.get_map()
        waypoint = mapping.get_waypoint(carla.Location(x=-40, y=1.75, z=1),
            project_to_road=False, lane_type=carla.LaneType.Driving)
        if waypoint is None:
            raise RuntimeError('Native approach lane survey failed')
        destination_waypoint = mapping.get_waypoint(
            carla.Location(x=RADIUS_M - 1.75, y=RADIUS_M, z=1),
            project_to_road=False, lane_type=carla.LaneType.Driving)
        if destination_waypoint is None or destination_waypoint.road_id == waypoint.road_id:
            raise RuntimeError('Native right-turn destination lane survey failed')
        _new(output / 'road_geometry.json', {'authored_map_sha256': hashlib.sha256(map_text.encode()).hexdigest(),
            'native_map_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'approach_road_id': waypoint.road_id, 'approach_lane_id': waypoint.lane_id,
            'destination_road_id': destination_waypoint.road_id,
            'destination_lane_id': destination_waypoint.lane_id,
            'area_classification': 'business_district',
            'area_classification_review_required': True, 'right_turn_destination_review_required': True,
            'provenance': 'original_native_capture'})
        vehicle_bp = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        vehicle_bp.set_attribute('role_name', 'c42417_ego')
        ego = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-APPROACH_M, y=1.75, z=.5), carla.Rotation(yaw=0)))
        owned.append(ego)
        sign_bp = world.get_blueprint_library().find('traffic.speed_limit.30')
        sign = world.spawn_actor(sign_bp, carla.Transform(
            carla.Location(x=-100, y=4.5, z=.2), carla.Rotation(yaw=180)))
        owned.append(sign)
        _new(output / 'control_context.json', {'control': 'speed_limit_sign',
            'native_actor_id': sign.id, 'native_blueprint': sign.type_id,
            'approach_road_id': waypoint.road_id, 'approach_lane_id': waypoint.lane_id,
            'legal_effect_not_inferred': True})
        for _ in range(40):
            world.tick()
        wheels = ego.get_physics_control().wheels
        if len(wheels) != 4:
            raise RuntimeError('Original Native wheel geometry missing')
        wheelbase = (max(w.position.x for w in wheels) - min(w.position.x for w in wheels)) / 100
        max_steer = max(w.max_steer_angle for w in wheels)
        controller = PathController([[x, -y] for x, y in route()], wheelbase, max_steer,
                                    EngineeringKnobs(target_speed_mps=10.0,
                                        lookahead_base_m=config['controller_lookahead_base_m']))
        _new(output / 'native-construction-context.json', {'case_id': config['case_id'],
            'wheelbase_m': wheelbase, 'max_steer_deg': max_steer,
            'signal_start_x_m': -config['signal_distance_m'],
            'requested_signal_distance_m': config['signal_distance_m'],
            'controller_lookahead_base_m': config['controller_lookahead_base_m'],
            'physical_success_claimed': False})
        for spec in camera_plan():
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in [('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', spec['fov_deg']), ('sensor_tick', 0)]:
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, _camera_pose(carla, spec),
                attach_to=ego if spec['attachment'] == 'ego' else None)
            owned.append(sensor)
            image_queues[spec['name']] = queue.Queue()
            sensor.listen(image_queues[spec['name']].put)
            logs[spec['name']] = (output / (spec['name'] + '.encoder.log')).open('x')
            encoders[spec['name']] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f"{spec['width']}x{spec['height']}", '-r', '20', '-i', 'pipe:0',
                '-an', '-c:v', 'ffv1', str(output / (spec['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=logs[spec['name']])
        pipeline = PipelineCapture(client, ego, output, config['case_id'],
            visibility=False, required_observations=config.get('required_atoms', []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        initial_heading = ego.get_transform().rotation.yaw
        with (output / 'native_samples.jsonl').open('x') as samples, \
             (output / 'video_frames.jsonl').open('x') as joins, \
             (output / 'body_history.jsonl').open('x') as bodies:
            for index in range(600):
                before = ego.get_transform()
                speed = _speed(ego)
                command = controller.step(position_xy_m=(before.location.x, before.location.y),
                    yaw_rad=math.radians(before.rotation.yaw), speed_mps=speed, dt_s=.05)
                requested = before.location.x >= -config['signal_distance_m']
                ego.set_light_state(carla.VehicleLightState.RightBlinker if requested
                                    else carla.VehicleLightState(0))
                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],
                    brake=command['brake'], steer=command['steer'],
                    hand_brake=command['hand_brake']))
                native_frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                road_waypoint = mapping.get_waypoint(pose.location,
                    project_to_road=False, lane_type=carla.LaneType.Driving)
                light_bits = int(ego.get_light_state())
                right_bit = int(carla.VehicleLightState.RightBlinker)
                row = {'provenance': 'original_native_capture', 'case_id': config['case_id'],
                    'sample_index': index, 'native_frame': native_frame, 'time_s': elapsed,
                    'ego_center_xy_m': [pose.location.x, pose.location.y],
                    'ego_heading_deg': pose.rotation.yaw, 'ego_speed_mps': _speed(ego),
                    'road_id': None if road_waypoint is None else road_waypoint.road_id,
                    'lane_id': None if road_waypoint is None else road_waypoint.lane_id,
                    'right_lamp_commanded': requested,
                    'right_lamp_observed': bool(light_bits & right_bit),
                    'course_change_observed': abs((pose.rotation.yaw - initial_heading + 180) % 360 - 180) >= 1.0,
                    'course_change_detection_tolerance_deg': 1.0,
                    'course_change_detection_tolerance_is_legal': False,
                    'area_classification': 'business_district', 'precipitation': 'rain',
                    'controller_request': command}
                pipeline.capture(native_frame, elapsed, extra={'c42417_native': row})
                samples.write(json.dumps(row, allow_nan=False) + '\n')
                vertices = ego.bounding_box.get_world_vertices(pose)
                bodies.write(json.dumps({'frame': native_frame, 'time_s': elapsed,
                    'road_id': None if road_waypoint is None else road_waypoint.road_id,
                    'lane_id': None if road_waypoint is None else road_waypoint.lane_id,
                    'body_vertices_m': [[v.x, v.y, v.z] for v in vertices]},
                    allow_nan=False) + '\n')
                for spec in camera_plan():
                    image = image_queues[spec['name']].get(timeout=30)
                    while image.frame < native_frame:
                        image = image_queues[spec['name']].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera/Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                joins.write(json.dumps({'video_frame': index, 'carla_frame': native_frame,
                    'native_frame': native_frame, 'time_s': elapsed}) + '\n')
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
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
                    raise RuntimeError('Encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        if world_changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        _new(output / 'native-capture-report.json', {'case_id': config['case_id'],
            'frames': frames, 'expected_frames': 600, 'restoration': restored,
            'error': error, 'accepted': False,
            'required_saved_checks': ['business-district source classification',
                'original lamp pixels and blinking', 'measured continuous signal distance',
                'full route/body, four-camera frame and physical motion review']})
    if error:
        raise RuntimeError('Native capture failed; inspect native-capture-report.json')
    return {'case_id': config['case_id'], 'frames': frames,
            'original_native_captured': True, 'accepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not (args.output_dir and args.host and args.port):
            parser.error('Supply --output-dir, --host and --port')
        print(json.dumps(capture(config, args.output_dir, args.host, args.port)))
