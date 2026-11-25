"""Executable C111088 Native capture proposal; no CARLA import on --check.

The runner writes original actor, signal, body, camera and Core capture sources.
An operator must provide an exclusive idle server; saved evidence must be
finalized and independently reviewed before any delivery selection.
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

from cameras import camera_plan
from controller import choose_action
from engineering import parameters
from geometry import INTERSECTION, check as geometry_check, overlap, road_xml


def write_new(path: Path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def check(case_id: str, candidate_id: str) -> dict:
    config = parameters(case_id, candidate_id)
    geometry = geometry_check()
    cameras = camera_plan(candidate_id)
    if config['rate_hz'] * config['duration_s'] != 840:
        raise ValueError('Exact 42-second contract differs')
    if [c['name'] for c in cameras] != ['overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('Four original camera streams differ')
    if len({tuple(c['xyz_m']) for c in cameras}) != 4:
        raise ValueError('Camera viewpoints are not distinct')
    return {'config': config, 'geometry': geometry, 'camera_count': 4,
            'native_imported': False, 'physical_success_claimed': False}


def body_xy(actor) -> list[list[float]]:
    pose = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(pose)
    points = {(round(v.x, 5), round(v.y, 5)) for v in vertices}
    if len(points) != 4:
        raise RuntimeError('Original Native body has no four-corner horizontal footprint')
    return [list(point) for point in sorted(points)]


def survey(carla, mapping, native_hash: str) -> dict:
    requests = {'ego_south': (1.75, -25, 3, [0, 1]),
                'other_west': (-20, -1.75, 1, [1, 0]),
                'north_exit': (1.75, 20, 4, [0, 1])}
    lanes = {}
    for name, (x, y, road, direction) in requests.items():
        wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=.2),
                                  project_to_road=False, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != road:
            raise RuntimeError('Original Native road survey differs: ' + name)
        vec = wp.transform.get_forward_vector()
        if vec.x * direction[0] + vec.y * direction[1] < .98:
            raise RuntimeError('Original Native lane direction differs: ' + name)
        lanes[name] = {'road_id': wp.road_id, 'lane_id': wp.lane_id,
                       'forward_xy': [vec.x, vec.y]}
    crossing = [p for p in mapping.get_crosswalks() if -5 <= p.x <= 5 and -13 <= p.y <= -9]
    if len(crossing) < 4:
        raise RuntimeError('Adjacent crosswalk not present in Native map readback')
    return {'native_map_sha256': native_hash, 'lanes': lanes,
            'adjacent_crosswalk_xy_m': [[p.x, p.y] for p in crossing],
            'intersection_bounds_xy_m': list(INTERSECTION),
            'stop_line_y_m': -14.0, 'authored_aspect': 'green_straight_arrow',
            'authored_aspect_source': 'road.xodr signal subtype 2',
            'pixel_aspect_verified': False}


def camera_transform(carla, spec):
    x, y, z = spec['xyz_m']
    if spec['attachment'] == 'ego':
        return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=-5))
    yaw = math.degrees(math.atan2(-y, -x))
    pitch = math.degrees(math.atan2(-z, math.hypot(x, y)))
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw, pitch=pitch))


def speed_m_s(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def execute(case_id: str, candidate_id: str, output: Path, host: str, port: int):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore

    checked = check(case_id, candidate_id)
    config = checked['config']
    output = output.resolve()
    materialized = output / 'config.json'
    if not output.is_dir() or not materialized.is_file():
        raise ValueError('Use a fresh materialized exact-case output directory')
    selected = json.loads(materialized.read_text())
    if any(selected.get(key) != config.get(key) for key in
           ('case_id', 'candidate_id', 'rate_hz', 'duration_s', 'knobs')):
        raise ValueError('Materialized exact construction differs from runner')
    if (output / 'native-capture-report.json').exists():
        raise ValueError('Retain prior Native attempt; use a fresh materialization')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    previous_world = client.get_world()
    if saved['settings'].synchronous_mode or [a for a in previous_world.get_actors()
        if a.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))]:
        raise RuntimeError('Requires exclusive idle asynchronous Native world')
    owned = []
    cameras = {}
    encoders = {}
    encoder_logs = {}
    capture = None
    changed = False
    restored = None
    error = None
    count = 0
    try:
        world = client.generate_opendrive_world(road_xml(), carla.OpendriveGenerationParameters(
            vertex_distance=.25, max_road_length=50, wall_height=0, additional_width=0,
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
        native_hash = hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()
        readback = survey(carla, mapping, native_hash)
        heads = list(world.get_actors().filter('traffic.traffic_light*'))
        if len(heads) < 2:
            raise RuntimeError('Both Native signal actors required')
        south = min(heads, key=lambda a: math.hypot(a.get_location().x, a.get_location().y + 13))
        west = min((a for a in heads if a.id != south.id),
                   key=lambda a: math.hypot(a.get_location().x + 13, a.get_location().y))
        if south.id == west.id:
            raise RuntimeError('Governing and prior-entry signal actor identities coincide')
        readback['south_signal_actor_id'] = south.id
        readback['west_signal_actor_id'] = west.id
        write_new(output / 'road_geometry.json', readback)
        library = world.get_blueprint_library()
        ego_bp = library.find('vehicle.lincoln.mkz_2020')
        ego_bp.set_attribute('role_name', 'c111088_ego')
        ego = world.spawn_actor(ego_bp, carla.Transform(
            carla.Location(x=1.75, y=config['knobs']['ego_spawn_y_m'], z=.5),
            carla.Rotation(yaw=90)))
        owned.append(ego)
        other_bp = library.find('vehicle.tesla.model3')
        other_bp.set_attribute('role_name', 'c111088_other')
        other = world.spawn_actor(other_bp, carla.Transform(
            carla.Location(x=config['knobs']['other_spawn_x_m'], y=-1.75, z=.5),
            carla.Rotation(yaw=0)))
        owned.append(other)
        ego.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        other.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(20):
            world.tick()
        write_new(output / 'native-construction-context.json', {
            'case_id': case_id, 'candidate_id': candidate_id,
            'native_map_sha256': native_hash, 'ego_actor_id': ego.id,
            'other_actor_id': other.id, 'ego_blueprint': ego.type_id,
            'other_blueprint': other.type_id, 'knobs': config['knobs'],
            'authored_intent': 'prior west entry, sole south straight arrow, straight ego yield',
            'physical_completion_claimed': False})
        for spec in camera_plan(candidate_id):
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', spec['fov_deg']), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, camera_transform(carla, spec),
                                       attach_to=ego if spec['attachment'] == 'ego' else None)
            owned.append(sensor)
            cameras[spec['name']] = queue.Queue()
            sensor.listen(cameras[spec['name']].put)
            encoder_logs[spec['name']] = (output / (spec['name'] + '.encoder.log')).open('x')
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f"{spec['width']}x{spec['height']}", '-r', '20', '-i', 'pipe:0',
                '-an', '-c:v', 'ffv1', '-level', '1', str(output / (spec['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=encoder_logs[spec['name']])
        capture = PipelineCapture(client, ego, output, case_id, visibility=False,
                                  required_observations=[])
        start = world.get_snapshot().timestamp.elapsed_seconds
        entered_lawfully = False
        prior_other_within = False
        clear_frames = 0
        with (output / 'native_samples.jsonl').open('x') as native_file, \
             (output / 'body_history.jsonl').open('x') as body_file, \
             (output / 'video_frames.jsonl').open('x') as frame_file:
            for index in range(840):
                arrow_active = index >= 100
                south.set_state(carla.TrafficLightState.Green if arrow_active else carla.TrafficLightState.Red)
                west.set_state(carla.TrafficLightState.Red if arrow_active else carla.TrafficLightState.Green)
                south.freeze(True)
                west.freeze(True)
                prior_body = body_xy(other)
                other_within = overlap(prior_body, INTERSECTION) > 0
                if config['lawful_conflict_participant_present'] and other.get_location().x < 12:
                    actual_speed = speed_m_s(other)
                    other.apply_control(carla.VehicleControl(
                        throttle=.42 if actual_speed < config['knobs']['cross_traffic_target_m_s'] else 0,
                        brake=0, hand_brake=False))
                else:
                    other.apply_control(carla.VehicleControl(throttle=0, brake=1))
                signal = {'frame': index, 'faces_ego': True,
                          'aspects': ['green_straight_arrow']}
                actor = {'frame': index, 'actor_id': str(other.id), 'kind': 'motor_vehicle',
                         'lawfully_within': entered_lawfully,
                         'within_intersection_or_adjacent_crosswalk': other_within}
                if arrow_active and str(south.get_state()) in ('Green', 'TrafficLightState.Green'):
                    action = choose_action(signal, [actor], frame=index)
                else:
                    action = {'route': 'straight', 'brake': 1.0, 'target_speed_m_s': 0.0,
                              'yielding_to_actor_ids': [], 'turn_command': 0.0}
                ego_speed = speed_m_s(ego)
                if action['brake']:
                    clear_frames = 0
                else:
                    clear_frames += 1
                margin = round(config['knobs']['clearance_margin_s'] * 20)
                hold = action['brake'] or clear_frames < margin
                ego.apply_control(carla.VehicleControl(
                    throttle=0 if hold else (.36 if ego_speed < config['knobs']['ego_target_m_s'] else 0),
                    brake=1 if hold else 0, steer=0, hand_brake=hold and ego_speed < .05))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                ego_pose = ego.get_transform()
                body = body_xy(ego)
                other_body = body_xy(other)
                other_occupied = overlap(other_body, INTERSECTION) > 0
                if other_occupied and not prior_other_within and not arrow_active and \
                   str(west.get_state()) in ('Green', 'TrafficLightState.Green'):
                    entered_lawfully = True
                prior_other_within = other_occupied
                sample = {'time_s': time_s, 'native_frame': frame,
                          'native_center_xy_m': [ego_pose.location.x, ego_pose.location.y],
                          'native_yaw_deg': ego_pose.rotation.yaw, 'native_body_xy_m': body,
                          'speed_mps': speed_m_s(ego),
                          'governing_signal': {
                              'native_actor_id': south.id, 'native_state': str(south.get_state()),
                              'authored_aspect': 'green_straight_arrow',
                              'authored_aspect_source': 'road.xodr subtype 2',
                              'facing_ego_native_survey': True, 'pixel_aspect_verified': False},
                          'other_vehicle': {
                              'native_actor_id': other.id, 'native_body_xy_m': other_body,
                              'within_intersection_or_adjacent_crosswalk': other_occupied,
                              'prior_green_entry_observed': entered_lawfully,
                              'west_native_signal_actor_id': west.id,
                              'west_native_state': str(west.get_state())},
                          'controller_request': action}
                capture.capture(frame, time_s, extra={'c111088_native': sample})
                native_file.write(json.dumps(sample, allow_nan=False) + '\n')
                body_file.write(json.dumps({'frame': frame, 'time_s': time_s,
                    'body_vertices_m': [[v.x, v.y, v.z] for v in
                                        ego.bounding_box.get_world_vertices(ego_pose)]},
                    allow_nan=False) + '\n')
                for spec in camera_plan(candidate_id):
                    image = cameras[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = cameras[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera/Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                frame_file.write(json.dumps({'video_frame': index, 'native_frame': frame,
                                              'carla_frame': frame, 'time_s': time_s}) + '\n')
                count += 1
        if count != 840:
            raise RuntimeError('Original 42-second capture incomplete')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
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
                    raise RuntimeError('Original lossless camera encode failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
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
        write_new(output / 'native-capture-report.json', {
            'case_id': case_id, 'candidate_id': candidate_id, 'frames': count,
            'expected_frames': 840, 'restoration': restored,
            'error': error, 'accepted': False,
            'saved_review_required': ['Native head direction and sole-arrow pixels',
                                      'prior lawful entry and conflict occupancy',
                                      'all four decoded source cameras and joins']})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-id')
    parser.add_argument('--candidate-id')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config_path = Path(__file__).resolve().parent / 'config.json'
    materialized = json.loads(config_path.read_text()) if config_path.is_file() else {}
    case_id = args.case_id or materialized.get('case_id')
    candidate_id = args.candidate_id or materialized.get('candidate_id')
    if not case_id or not candidate_id:
        parser.error('Provide exact case and candidate, or use a materialized config.json')
    if materialized and (materialized.get('case_id') != case_id or
                         materialized.get('candidate_id') != candidate_id):
        parser.error('CLI case or candidate differs from materialized construction')
    if args.check:
        print(json.dumps(check(case_id, candidate_id), allow_nan=False))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Provide a new output directory and owned Native endpoint')
        execute(case_id, candidate_id, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
