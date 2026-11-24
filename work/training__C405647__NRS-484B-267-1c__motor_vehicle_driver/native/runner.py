"""Prospective Native acquisition for emergency whole-body passage.

CPU --check reads the exact inline request. Capture requires an exclusively owned
idle CARLA world; it records observed motion and original pixels without claiming
qualifying lights, authority, officer direction, or legal compliance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from emergency_wait import check_config, read_and_measure


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def offline_check(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    if config['road_sha256'] != digest(root / 'emergency-road.xodr'):
        raise ValueError('Exact road source hash differs')
    result = check_config(config, (root / 'emergency-road.xodr').read_text())
    result['request_measure'] = read_and_measure(root / 'requested-track.jsonl',
                                                'authored_native_request')
    result['candidate_id'] = config['candidate_id']
    return result


def body_xy(actor):
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in
                     actor.bounding_box.get_world_vertices(actor.get_transform())})
    if len(points) != 4:
        raise RuntimeError('Original Native body footprint lacks four XY corners')
    return [list(point) for point in points]


def control(carla, actor, target_xy, speed_target, wheelbase, max_steer):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    dx, dy = target_xy[0] - pose.location.x, target_xy[1] - pose.location.y
    alpha = math.atan2(dy, dx) - math.radians(pose.rotation.yaw)
    alpha = math.atan2(math.sin(alpha), math.cos(alpha))
    steer = max(-0.8, min(0.8, math.atan2(2 * wheelbase * math.sin(alpha),
                                         max(0.2, math.hypot(dx, dy))) /
                          math.radians(max_steer)))
    error = speed_target - speed
    throttle = 0 if speed_target < 0.05 else max(0., min(1., .2 + .35 * error))
    brake = 1 if speed_target < 0.05 else max(0., min(1., -.35 * error))
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer), {
        'target_xy_m': target_xy, 'target_speed_mps': speed_target,
        'observed_speed_mps': speed, 'pose_error_m': math.hypot(dx, dy)}


def camera_pose(carla, spec):
    x, y, z = spec['location_xyz_m']
    pitch, roll, yaw = spec['rotation_pyr_deg']
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, roll=roll, yaw=yaw))


def capture(output_dir, host, port):
    import carla
    import numpy as np
    from worker_exchange.world_restore import snapshot, restore

    root = Path(__file__).resolve().parent
    output = Path(output_dir).resolve()
    if output != root:
        raise ValueError('Capture must write into the materialized exact-case attempt')
    preflight = offline_check(root)
    config = json.loads((root / 'config.json').read_text())
    requests = [json.loads(line) for line in (root / 'requested-track.jsonl').read_text().splitlines()]
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    previous = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.')) for a in previous.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    actors, encoders, logs, image_queues = [], {}, {}, {}
    changed, frames, error, restored = False, 0, None, None
    try:
        xml = (root / 'emergency-road.xodr').read_text()
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
        library = world.get_blueprint_library()
        subject_bp = library.find('vehicle.lincoln.mkz_2020')
        emergency_bp = library.find('vehicle.ford.ambulance')
        subject_bp.set_attribute('role_name', 'c405647_subject')
        emergency_bp.set_attribute('role_name', 'c405647_emergency_request')
        first = requests[0]
        subject = world.spawn_actor(subject_bp, carla.Transform(
            carla.Location(x=first['ego_center_xy_m'][0], y=first['ego_center_xy_m'][1], z=.5),
            carla.Rotation(yaw=90)))
        emergency = world.spawn_actor(emergency_bp, carla.Transform(
            carla.Location(x=first['emergency_center_xy_m'][0],
                           y=first['emergency_center_xy_m'][1], z=.5), carla.Rotation(yaw=90)))
        actors.extend((subject, emergency))
        for actor in (subject, emergency):
            actor.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(40):
            world.tick()
        geometry = {}
        for name, actor, expected_lane in (('subject', subject, -2), ('emergency', emergency, -1)):
            waypoint = mapping.get_waypoint(actor.get_transform().location,
                                            project_to_road=False, lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != expected_lane:
                raise RuntimeError(name + ' original Native lane differs from authored lane')
            wheels = actor.get_physics_control().wheels
            if len(wheels) != 4:
                raise RuntimeError(name + ' original Native wheel geometry incomplete')
            wheelbase = (max(w.position.x for w in wheels) - min(w.position.x for w in wheels)) / 100
            max_steer = max(w.max_steer_angle for w in wheels)
            if wheelbase <= 0 or max_steer <= 0:
                raise RuntimeError(name + ' original Native wheel geometry invalid')
            geometry[name] = wheelbase, max_steer
        (output / 'native-map-readback.json').write_text(json.dumps({
            'original_opendrive_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'original_start_lanes': {'subject': -2, 'emergency': -1},
            'physical_completion': False}, indent=2) + '\n')
        for spec in config['cameras']:
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', spec['fov_deg']), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            camera = world.spawn_actor(bp, camera_pose(carla, spec))
            actors.append(camera)
            image_queues[spec['name']] = queue.Queue()
            camera.listen(image_queues[spec['name']].put)
            log = (output / (spec['name'] + '.encoder.log')).open('x')
            logs[spec['name']] = log
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s',
                f"{spec['width']}x{spec['height']}", '-r', '20', '-i', 'pipe:0',
                '-an', '-c:v', 'ffv1', '-level', '1', str(output / (spec['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=log)
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'observed-actors.jsonl').open('x') as actor_file, \
             (output / 'video_frames.jsonl').open('x') as video_file:
            for index, request in enumerate(requests):
                commands = {}
                for name, actor, source, target_speed in (
                    ('subject', subject, 'ego_center_xy_m', request['ego_speed_mps']),
                    ('emergency', emergency, 'emergency_center_xy_m',
                     config['requested_emergency_step_y_m_per_frame'] * 20)):
                    target = requests[min(599, index + 20)][source]
                    command, packet = control(carla, actor, target, target_speed,
                                              *geometry[name])
                    actor.apply_control(command)
                    commands[name] = packet
                emergency.set_light_state(carla.VehicleLightState(
                    carla.VehicleLightState.Special1 if index % 10 < 5
                    else carla.VehicleLightState.NONE))
                frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start
                observed = {}
                for name, actor in (('subject', subject), ('emergency', emergency)):
                    pose = actor.get_transform()
                    velocity = actor.get_velocity()
                    waypoint = mapping.get_waypoint(pose.location, project_to_road=False,
                                                    lane_type=carla.LaneType.Driving)
                    observed[name] = {'native_center_xy_m': [pose.location.x, pose.location.y],
                                      'native_body_xy_m': body_xy(actor),
                                      'native_speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
                                      'native_yaw_deg': pose.rotation.yaw,
                                      'native_road_id': None if waypoint is None else waypoint.road_id,
                                      'native_lane_id': None if waypoint is None else waypoint.lane_id,
                                      'control_request': commands[name]}
                actor_file.write(json.dumps({
                    'frame': index, 'native_frame': frame, 'time_s': elapsed,
                    'source_kind': 'original_native', 'actors': observed,
                    'special1_requested': index % 10 < 5,
                    'special1_observed': bool(emergency.get_light_state() &
                                              carla.VehicleLightState.Special1),
                    'qualifying_front_lamp': None,
                    'authority_verified': None,
                    'officer_direction_verified': None}, allow_nan=False) + '\n')
                for spec in config['cameras']:
                    image = image_queues[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = image_queues[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera and Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                video_file.write(json.dumps({'video_frame': index, 'native_frame': frame,
                                             'carla_frame': frame, 'time_s': elapsed}) + '\n')
                frames += 1
        if frames != 600:
            raise RuntimeError('Original Native frame count incomplete')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        for name, process in encoders.items():
            try:
                process.stdin.close()
                code = process.wait(timeout=180)
                if code:
                    raise RuntimeError(name + ' FFV1 encoder exited ' + str(code))
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
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
        (output / 'native-capture-report.json').write_text(json.dumps({
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'frames': frames, 'expected_frames': 600, 'restoration': restored,
            'error': error, 'accepted': False, 'qualification_verified': False},
            indent=2) + '\n')
    if error:
        raise RuntimeError('Native capture failed; inspect native-capture-report.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(offline_check(Path.cwd()), sort_keys=True))
        return
    if not all((args.output_dir, args.host, args.port)):
        parser.error('Native capture requires --output-dir, --host and --port')
    capture(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
