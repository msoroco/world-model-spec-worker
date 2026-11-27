"""Prospective original Native person-interaction capture for NRS 484B.653(1)(a).

Runs only under exclusive local CARLA ownership. Source packets and telemetry are
retained for independent review; no mental-state or legal finding is made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import queue
import subprocess
from pathlib import Path

from native.person_interaction import FRAME_COUNT, FRAME_RATE, control_request
from native.person_scene import (EGO_START_X_M, LANE_WIDTH_M, MODES, WORKER_X_M,
                                 WORKER_Y_M, inspect, open_drive, require_source_packet)

ASSIGNMENT = 'training__C179799__NRS-484B-653-1a__motor_vehicle_driver'
CASE_PREFIX = ASSIGNMENT + '__selected_ce719cfa__'
CAMERAS = (
    ('overview', 1920, 1080, -18, -14, 12, -22),
    ('approach', 1280, 720, -12, -4, 5, -10),
    ('reference_corner', 1280, 720, 0, -8, 5, -12),
    ('driver_reference', 1280, 720, -2, 0, 3, -7),
)


def check(config):
    suffix = config.get('case_id', '').removeprefix(CASE_PREFIX)
    if (config.get('case_id') != CASE_PREFIX + suffix or suffix not in MODES
            or config.get('interaction_mode') != MODES[suffix]):
        raise ValueError('Selected person interaction identity or response mode changed')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-653-1a', 'C179799', 'motor_vehicle_driver'):
        raise ValueError('Frozen law, cell or actor changed')
    if config.get('duration_s') != 30 or config.get('rate_hz') != FRAME_RATE:
        raise ValueError('Thirty-second original capture changed')
    if not -5.5 <= config.get('worker_y_m', -5.2) <= -4.6:
        raise ValueError('Roadside worker engineering offset changed scope')
    if [(c.get('name'), c.get('width'), c.get('height')) for c in config.get('cameras', [])] != [
            (name, width, height) for name, width, height, *_ in CAMERAS]:
        raise ValueError('Four original source cameras changed')
    if config.get('physical_verified') is not False or config.get('legal_verdict') is not None:
        raise ValueError('Prospective case cannot assert physical or legal success')
    return {'case_id': config['case_id'], 'authored_geometry': inspect(),
            'frames': FRAME_COUNT, 'native_imported': False,
            'physical_verified': False, 'legal_verdict': None}


def _write_new(path, content):
    with Path(path).open('x') as stream:
        json.dump(content, stream, indent=2, allow_nan=False)
        stream.write('\n')


def _speed(actor):
    velocity = actor.get_velocity()
    return math.hypot(velocity.x, velocity.y)


def _source_packet(path, case_id):
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError('Independent original context packet missing')
    packet = require_source_packet(json.loads(source.read_text()), case_id)
    for key, value in packet.items():
        if key.endswith('_source') and isinstance(value, dict):
            document = Path(value.get('path', ''))
            if not document.is_file() or hashlib.sha256(document.read_bytes()).hexdigest() != value.get('sha256'):
                raise ValueError('Changed original context source: ' + key)
    return source, packet


def execute(config, output_dir, context_packet, host='127.0.0.1', port=2000):
    check(config)
    source, packet = _source_packet(context_packet, config['case_id'])
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output_dir).resolve()
    if not (output / 'config.json').is_file() or any((output / name).exists() for name in (
            'native-person-interaction.jsonl', 'video_frames.jsonl', 'native-capture-report.json')):
        raise ValueError('Choose a fresh materialized original Native attempt directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    if saved['settings'].synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in client.get_world().get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, encoders, cameras = [], {}, {}
    capture, changed, failure, frames, restoration = None, False, None, 0, None
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0,
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
        mapping = world.get_map()
        road_xml = mapping.to_opendrive()
        driving = mapping.get_waypoint(carla.Location(x=-60, y=-1.75, z=.5),
                                      project_to_road=False, lane_type=carla.LaneType.Driving)
        if driving is None or driving.road_id != 1 or driving.lane_id != -1:
            raise RuntimeError('Native paved driving lane readback failed')
        output.mkdir(parents=True, exist_ok=True)
        (output / 'road.xodr').write_text(road_xml)
        (output / 'original-context-packet.json').write_bytes(source.read_bytes())
        _write_new(output / 'native-road-readback.json', {
            'source_kind': 'original_native_map_readback',
            'map_sha256': hashlib.sha256(road_xml.encode()).hexdigest(),
            'driving_road_id': driving.road_id, 'driving_lane_id': driving.lane_id,
            'driving_lane_width_m': driving.lane_width,
            'worker_route_relation_requested': inspect()['worker_relation'],
            'highway_or_public_access_verified': False,
            'surface_and_sight_lines_verified': False})
        library = world.get_blueprint_library()
        vehicle_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        vehicle_bp.set_attribute('role_name', 'c179799_subject_driver')
        ego = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=EGO_START_X_M, y=-LANE_WIDTH_M/2, z=.7),
            carla.Rotation(yaw=0)))
        owned.append(ego)
        worker_bp = sorted(library.filter('walker.pedestrian.*'), key=lambda b: b.id)[0]
        worker_bp.set_attribute('role_name', 'c179799_roadside_worker')
        worker_y = config.get('worker_y_m', WORKER_Y_M)
        worker = world.spawn_actor(worker_bp, carla.Transform(
            carla.Location(x=WORKER_X_M, y=worker_y, z=.8),
            carla.Rotation(yaw=90)))
        owned.append(worker)
        if worker.id == ego.id or not worker.type_id.startswith('walker.pedestrian.'):
            raise RuntimeError('Distinct original person actor missing')
        collision_events = queue.Queue()
        collision_bp = library.find('sensor.other.collision')
        collision = world.spawn_actor(collision_bp, carla.Transform(), attach_to=ego)
        owned.append(collision)
        collision.listen(collision_events.put)
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', '.05')
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)),
                attach_to=ego)
            owned.append(camera)
            cameras[name] = queue.Queue()
            camera.listen(cameras[name].put)
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', '20', '-i', '-', '-frames:v', str(FRAME_COUNT),
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with PipelineCapture(client, ego, output, config['case_id'],
                             required_observations=config.get('required_atoms', [])) as capture, (
                FrameMap(output / 'video_frames.jsonl')) as frame_map, (
                output / 'native-person-interaction.jsonl').open('x') as raw:
            first_elapsed = None
            last_yaw = None
            for index in range(FRAME_COUNT):
                before = ego.get_transform()
                forward_gap = WORKER_X_M - before.location.x
                request = control_request(config['interaction_mode'],
                                          forward_gap if forward_gap >= 0 else 100.0)
                yaw_now = math.radians(before.rotation.yaw)
                yaw_rate = 0.0 if last_yaw is None else (yaw_now - last_yaw) * FRAME_RATE
                last_yaw = yaw_now
                desired_speed = 8.0
                speed = _speed(ego)
                throttle = min(.55, max(0.0, (desired_speed-speed)*.18)) if request['brake'] == 0 else 0.0
                command = carla.VehicleControl(throttle=throttle, brake=request['brake'], steer=0.0)
                ego.apply_control(command)
                worker.apply_control(carla.WalkerControl(direction=carla.Vector3D(0, 0, 0), speed=0.0))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Original Native tick identity changed')
                if first_elapsed is None:
                    first_elapsed = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - first_elapsed
                pose, velocity, accel = ego.get_transform(), ego.get_velocity(), ego.get_acceleration()
                person_pose, person_velocity = worker.get_transform(), worker.get_velocity()
                contacts = []
                while not collision_events.empty():
                    event = collision_events.get_nowait()
                    contacts.append({'frame': event.frame, 'other_actor_id': event.other_actor.id})
                source_row = {'frame': index, 'native_frame': native_frame,
                              'time_s': index/FRAME_RATE, 'native_time_s': time_s,
                              'ego_actor_id': ego.id, 'ego_blueprint_id': ego.type_id,
                              'ego_x_m': pose.location.x, 'ego_y_m': pose.location.y,
                              'ego_vx_mps': velocity.x, 'ego_vy_mps': velocity.y,
                              'ego_radius_m': math.hypot(ego.bounding_box.extent.x,
                                                         ego.bounding_box.extent.y),
                              'ego_accel_longitudinal_mps2': accel.x,
                              'ego_yaw_rate_radps': yaw_rate,
                              'person_actor_id': worker.id,
                              'person_blueprint_id': worker.type_id,
                              'person_x_m': person_pose.location.x,
                              'person_y_m': person_pose.location.y,
                              'person_vx_mps': person_velocity.x,
                              'person_vy_mps': person_velocity.y,
                              'person_radius_m': math.hypot(worker.bounding_box.extent.x,
                                                            worker.bounding_box.extent.y),
                              'collision_sensor_contact': any(e['other_actor_id'] == worker.id
                                                              and e['frame'] == native_frame for e in contacts),
                              'collision_events': contacts,
                              'control_readback': {'throttle': ego.get_control().throttle,
                                                   'brake': ego.get_control().brake,
                                                   'steer': ego.get_control().steer}}
                camera_frames = {}
                for name, q in cameras.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera and Native frame join failed')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                raw.write(json.dumps(source_row, allow_nan=False) + '\n')
                capture.capture(native_frame, time_s, extra={'person_interaction': source_row})
                frames += 1
        if frames != FRAME_COUNT:
            raise RuntimeError('Incomplete original Native encounter')
        _write_new(output / 'capture-intent.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'original_context_packet_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'original_person_actor_id': worker.id, 'original_vehicle_actor_id': ego.id,
            'person_role_requested': packet['worker_role_source'],
            'public_access_and_role_verified': False,
            'physical_verified': False, 'legal_verdict': None})
    except BaseException as exc:
        failure = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        for name, process in encoders.items():
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            try:
                stderr = process.stderr.read() if process.stderr else b''
                if process.wait(timeout=180) != 0:
                    failure = failure or {'encoder_error': name + ': ' + stderr.decode()[-400:]}
            except BaseException as exc:
                process.kill(); process.wait()
                failure = failure or {'encoder_error': str(exc)}
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.'):
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                failure = failure or {'actor_cleanup_error': str(exc)}
        if changed:
            try:
                restoration = restore(client, saved)
            except BaseException as exc:
                failure = failure or {'world_restore_error': str(exc)}
        if output.exists():
            _write_new(output / 'native-capture-report.json', {
                'case_id': config['case_id'], 'frames': frames,
                'expected_frames': FRAME_COUNT, 'restoration': restoration,
                'error': failure, 'physical_verified': False,
                'required_saved_checks': ['public highway or access-premises status and exclusions',
                                         'conventional vehicle and driving person',
                                         'roadside worker identity, role, position and motion',
                                         'complete timeline, nearby property, sight lines and surface',
                                         'original four-camera pixels and independent review',
                                         'willful or wanton mental state remains unresolved']})
    if failure:
        raise RuntimeError('Original Native attempt failed: ' + str(failure))
    return {'case_id': config['case_id'], 'frames': frames,
            'physical_verified': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--context-packet')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if args.check:
        print(json.dumps(check(config), indent=2))
    else:
        packet = args.context_packet or os.environ.get('SCENARIO_ORIGINAL_CONTEXT_PACKET')
        if not args.output_dir or not packet:
            raise ValueError('Local Native capture needs output and original context packet')
        print(json.dumps(execute(config, args.output_dir, packet,
                                 args.host, args.port), indent=2))
