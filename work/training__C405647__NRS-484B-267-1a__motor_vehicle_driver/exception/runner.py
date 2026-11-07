"""Proposed original Native capture for the C405647 officer-direction pair.

``--check`` is CPU only. Physical execution needs exclusive ownership of an
idle CARLA server. It saves original frames and observed actor poses, but never
equates a requested light state with a qualifying red lamp or accepts a run.
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

from build import CASES, CANDIDATES, native_requests
from candidates import construction
from official_motion import check as geometry_check, open_drive

ROOT = Path(__file__).resolve().parent


def _write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def check(case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown case or candidate')
    geometry_check()
    plan = construction(case, candidate)
    tracks = native_requests(case, candidate)
    assert len(tracks) == 480 and len(plan['camera_plan']) == 5
    assert [camera['name'] for camera in plan['camera_plan']] == [
        'overview', 'front_lamp', 'rear_approach', 'subject_reference', 'officer_reference']
    assert [(camera['width'], camera['height']) for camera in plan['camera_plan']] == [
        (1920, 1080), (1280, 720), (1280, 720), (1280, 720), (1280, 720)]
    assert all(a['approach_request'] == b['approach_request'] and
               a['lamp_request'] == b['lamp_request'] and
               a['subject_request'] == b['subject_request'] for a, b in zip(
                   tracks, native_requests('exception_1_2' if case == 'exception_1_1'
                                           else 'exception_1_1', candidate)))
    assert all(not r['officer_direction_request']['actual_direction_observed']
               for r in tracks)
    return {'passed': True, 'case_suffix': case, 'candidate_id': candidate,
            'native_track_rows': len(tracks), 'camera_count': 5,
            'candidate_sha256': hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
            'carla_imported': False, 'original_pixels_seen': False,
            'physical_success_claimed': False}


def _body_native_xy(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
    if len(points) != 4:
        raise RuntimeError('Native body footprint lacks four distinct XY vertices')
    return [list(point) for point in points]


def _control(carla, actor, target, *, target_speed_mps, wheelbase_m, max_steer_deg):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    dx, dy = target['x_m'] - pose.location.x, target['y_m'] - pose.location.y
    alpha = math.atan2(dy, dx) - math.radians(pose.rotation.yaw)
    alpha = math.atan2(math.sin(alpha), math.cos(alpha))
    steer_radians = math.atan2(2 * wheelbase_m * math.sin(alpha), max(0.1, math.hypot(dx, dy)))
    steer = max(-0.8, min(0.8, steer_radians / math.radians(max_steer_deg)))
    error = target_speed_mps - speed
    throttle = max(0., min(1., 0.15 + 0.4 * error))
    brake = max(0., min(1., -0.4 * error))
    command = carla.VehicleControl(throttle=throttle, brake=brake, steer=steer)
    return command, {'throttle': throttle, 'brake': brake, 'steer': steer,
                     'target_native_xy_m': [target['x_m'], target['y_m']],
                     'target_speed_mps': target_speed_mps, 'observed_speed_mps': speed,
                     'observed_pose_error_m': math.hypot(dx, dy)}


def _camera_pose(carla, spec):
    x, authored_y, z = spec['xyz_m']
    if spec['attachment'] == 'world':
        # OpenDRIVE right lanes are reflected into the imported CARLA world.
        y = -authored_y
        aim_x, aim_y, aim_z = (40, 1.75, 1.5) if spec['name'] == 'front_lamp' else (45, 3.5, 0)
        yaw = math.degrees(math.atan2(aim_y - y, aim_x - x))
        pitch = math.degrees(math.atan2(aim_z - z, math.hypot(aim_x - x, aim_y - y)))
    else:
        y = authored_y
        yaw, pitch = 0, 0
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw, pitch=pitch))


def execute(case, candidate, output, host, port):
    import carla
    import numpy as np
    from worker_exchange.world_restore import snapshot, restore

    preflight = check(case, candidate)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use an existing exact-case materialized bundle directory')
    bundle_config = json.loads((output / 'config.json').read_text())
    if bundle_config.get('case_suffix') != case or bundle_config.get('candidate_id') != candidate:
        raise ValueError('Materialized case or candidate differs from requested capture')
    plan = construction(case, candidate)
    tracks = native_requests(case, candidate)
    _write_new(output / 'native-plan.json', plan)
    _write_new(output / 'cpu-preflight.json', preflight)
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    original = client.get_world()
    if saved['settings'].synchronous_mode or [actor for actor in original.get_actors()
                                                if actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))]:
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    actors, encoders, encoder_logs, queues = [], {}, {}, {}
    changed, frames, error, restored = False, 0, None, None
    try:
        xml = open_drive()
        (output / 'scene.xodr').write_text(xml)
        world = client.generate_opendrive_world(xml, carla.OpendriveGenerationParameters(
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
        native_xml = mapping.to_opendrive()
        native_hash = hashlib.sha256(native_xml.encode()).hexdigest()
        library = world.get_blueprint_library()
        # This blueprint is an authored visual stand-in. Its role name and
        # appearance do not establish official regulatory agency authority.
        subject_bp = library.find('vehicle.lincoln.mkz_2020')
        emergency_bp = library.find('vehicle.dodge.charger_police_2020')
        subject_bp.set_attribute('role_name', 'c405647_subject')
        emergency_bp.set_attribute('role_name', 'c405647_emergency_request')
        # A pedestrian blueprint is a visible stand-in only. CARLA does not
        # establish law-enforcement identity or communicate the legal content.
        officer_bp = library.find('walker.pedestrian.0001')
        officer_bp.set_attribute('role_name', 'c405647_officer_visual_request')
        first = tracks[0]
        subject = world.spawn_actor(subject_bp, carla.Transform(carla.Location(
            x=first['subject_request']['x_m'], y=first['subject_request']['y_m'], z=.5)))
        actors.append(subject)
        approach = world.spawn_actor(emergency_bp, carla.Transform(carla.Location(
            x=first['approach_request']['x_m'], y=first['approach_request']['y_m'], z=.5)))
        actors.append(approach)
        officer = world.spawn_actor(officer_bp, carla.Transform(carla.Location(
            x=first['officer_position_request_xy_m'][0],
            y=first['officer_position_request_xy_m'][1], z=.5)))
        actors.append(officer)
        subject.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        approach.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(40):
            world.tick()
        geometry = {}
        for name, actor, lane_id in (('subject', subject, -1), ('approach', approach, -1)):
            pose = actor.get_transform()
            lane = mapping.get_waypoint(pose.location, project_to_road=False,
                                        lane_type=carla.LaneType.Driving)
            if lane is None or lane.road_id != 1 or lane.lane_id != lane_id:
                raise RuntimeError(name + ' actual Native starting lane differs from authored road')
            wheels = actor.get_physics_control().wheels
            if len(wheels) != 4:
                raise RuntimeError(name + ' Native wheel geometry absent')
            wheelbase = (max(w.position.x for w in wheels) - min(w.position.x for w in wheels)) / 100
            max_steer = max(w.max_steer_angle for w in wheels)
            if wheelbase <= 0 or max_steer <= 0:
                raise RuntimeError(name + ' invalid Native wheel geometry')
            geometry[name] = (wheelbase, max_steer)
        _write_new(output / 'native-map-readback.json', {
            'native_opendrive_sha256': native_hash, 'observed_initial_lanes':
                {'subject': -1, 'approach': -1}, 'physical_success_claimed': False})
        for spec in plan['camera_plan']:
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', spec['fov_deg']), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            camera = world.spawn_actor(bp, _camera_pose(carla, spec),
                                       attach_to=subject if spec['attachment'] == 'subject' else None)
            actors.append(camera)
            queues[spec['name']] = queue.Queue()
            camera.listen(queues[spec['name']].put)
            log = (output / (spec['name'] + '.encoder.log')).open('x')
            encoder_logs[spec['name']] = log
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s',
                f"{spec['width']}x{spec['height']}", '-r', '20', '-i', 'pipe:0',
                '-an', '-c:v', 'ffv1', '-level', '1', str(output / (spec['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=log)
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'observed-actors.jsonl').open('x') as actor_file, \
             (output / 'video_frames.jsonl').open('x') as video_file:
            for index, request in enumerate(tracks):
                commands = {}
                for name, actor, key, target_speed in (
                    ('subject', subject, 'subject_request', 3),
                    ('approach', approach, 'approach_request', 8)):
                    target = tracks[min(479, index + 20)][key]
                    command, packet = _control(carla, actor, target,
                                                target_speed_mps=target_speed,
                                                wheelbase_m=geometry[name][0],
                                                max_steer_deg=geometry[name][1])
                    actor.apply_control(command)
                    commands[name] = packet
                requested_special = request['lamp_request']['front_red_flash_on']
                approach.set_light_state(carla.VehicleLightState(
                    carla.VehicleLightState.Special1 if requested_special else carla.VehicleLightState.NONE))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                observed = {}
                for name, actor in (('subject', subject), ('approach', approach)):
                    pose = actor.get_transform()
                    lane = mapping.get_waypoint(pose.location, project_to_road=False,
                                                lane_type=carla.LaneType.Driving)
                    observed[name] = {'native_center_xy_m': [pose.location.x, pose.location.y],
                                      'native_body_xy_m': _body_native_xy(actor),
                                      'native_yaw_deg': pose.rotation.yaw,
                                      'native_road_id': None if lane is None else lane.road_id,
                                      'native_lane_id': None if lane is None else lane.lane_id,
                                      'control_request': commands[name]}
                actor_file.write(json.dumps({
                    'frame': index, 'native_frame': frame, 'time_s': time_s,
                    'source_kind': 'original_native', 'actors': observed,
                    'officer_visual_native_center_xy_m': [officer.get_location().x,
                                                          officer.get_location().y],
                    'officer_direction_requested':
                        request['officer_direction_request']['requested'],
                    'officer_direction_content_requested':
                        request['officer_direction_request']['content'],
                    'actual_direction_identity_content_recipient_observed': None,
                    'special1_requested': requested_special,
                    'special1_observed': bool(approach.get_light_state() & carla.VehicleLightState.Special1),
                    'front_red_flash_on': None,
                    'front_red_flash_requires_original_pixel_review': True}, allow_nan=False) + '\n')
                for spec in plan['camera_plan']:
                    image = queues[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = queues[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera and Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                video_file.write(json.dumps({'video_frame': index, 'native_frame': frame,
                                             'carla_frame': frame,
                                             'time_s': time_s}, allow_nan=False) + '\n')
                frames += 1
        if frames != 480:
            raise RuntimeError('Original Native frame count incomplete')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        for name, process in encoders.items():
            try:
                process.stdin.close()
                code = process.wait(timeout=180)
                if code != 0:
                    raise RuntimeError(name + ' lossless encoder exited ' + str(code))
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for actor in reversed(actors):
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
        _write_new(output / 'native-capture-report.json', {
            'case_suffix': case, 'candidate_id': candidate, 'frames': frames,
            'expected_frames': 480, 'restoration': restored, 'error': error,
            'accepted': False, 'front_red_lamp_qualified': False,
            'vehicle_authority_verified': False,
            'officer_identity_or_direction_verified': False,
            'officer_actor_visual_stand_in_only': True,
            'saved_processing_requires_original_pixel_annotation': True})
    if error:
        raise RuntimeError('Native capture failed; inspect native-capture-report.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--candidate', choices=CANDIDATES)
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config_path = ROOT / 'config.json'
    config = json.loads(config_path.read_text()) if config_path.is_file() else {}
    case = args.case or config.get('case_suffix')
    candidate = args.candidate or config.get('candidate_id')
    if case not in CASES or candidate not in CANDIDATES:
        parser.error('Supply a known case and candidate, or materialize config.json')
    if args.check:
        print(json.dumps(check(case, candidate), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Physical capture requires --output-dir, --host and --port')
        execute(case, candidate, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
