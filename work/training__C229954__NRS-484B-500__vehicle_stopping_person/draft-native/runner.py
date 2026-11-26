"""Unselected C229954 Native stop proposal; original device source is mandatory."""

import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

from stop_controller import FRAMES, command
from route_contract import validate as validate_route

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
BASE = 'training__C229954__NRS-484B-500__vehicle_stopping_person__selected_d67fe2ae__'
ACTIVITIES = ('stop', 'stand', 'park')


def _identity(case_id):
    if not isinstance(case_id, str) or not case_id.startswith(BASE):
        raise ValueError('Wrong exact case identity')
    suffix = case_id.removeprefix(BASE)
    activity = 'stop'
    if suffix.startswith('stand_'):
        activity, suffix = 'stand', suffix.removeprefix('stand_')
    elif suffix.startswith('park_'):
        activity, suffix = 'park', suffix.removeprefix('park_')
    if suffix not in ('condition_a', 'condition_b'):
        raise ValueError('Unknown exact comparison condition')
    return activity, suffix


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(config):
    activity, condition = _identity(config.get('case_id'))
    require(config.get('activity_mode') == activity and config.get('law_id') == 'NRS-484B-500'
            and config.get('cell_id') == 'C229954'
            and config.get('actor') == 'vehicle_stopping_person'
            and config.get('frozen_cell') == {'layout': 'road', 'maneuver': 'stop_stand',
                                               'control': 'parking_restriction_device'},
            'Wrong exact case, law, actor or frozen cell')
    require(config.get('rate_hz') == 20 and config.get('duration_s') == 30
            and config.get('frames') == FRAMES, 'Full 600-frame capture required')
    cameras = config.get('cameras')
    require(isinstance(cameras, list) and tuple(x.get('name') for x in cameras) == VIEWS,
            'Four named source cameras required')
    for camera in cameras:
        require(all(type(camera.get(key)) is int and camera[key] >= 16
                    for key in ('width', 'height')) and camera.get('fps') == 20
                and len(camera.get('location_xyz_m', [])) == 3
                and len(camera.get('rotation_pyr_deg', [])) == 3,
                'Camera optics or pose missing')
    require(type(config.get('spawn_point_index')) is int and
            config['spawn_point_index'] >= 0 and
            config.get('vehicle_blueprint') == 'vehicle.tesla.model3',
            'Vehicle spawn proposal invalid')
    require(config.get('device_source_required') is True and
            config.get('device_designation_not_inferred_from_pose') is True and
            config.get('physical_completion') is False and
            config.get('legal_verdict') is None,
            'Original device provenance or outcome guard missing')
    require(config.get('controller') == 'observed_route_distance_stop_hold',
            'Controller policy differs')
    return {'case_id': config['case_id'], 'activity_mode': activity,
            'condition': condition, 'frames': FRAMES, 'rate_hz': 20,
            'source_views': list(VIEWS), 'device_source_required': True,
            'physical_completion': False, 'legal_verdict': None,
            'carla_contacted': False}


def _source(path, condition):
    source = json.loads(Path(path).read_text())
    return validate_route(source, condition)


def _xyz(vector):
    return [vector.x, vector.y, vector.z]


def _body_footprint(vertices):
    """Convex XY hull of the observed Native vehicle bounding-box vertices."""
    points = sorted({(float(vertex.x), float(vertex.y)) for vertex in vertices})
    if len(points) < 3:
        raise ValueError('Original vehicle body footprint is degenerate')
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    lower = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        raise ValueError('Original vehicle body footprint is degenerate')
    return [list(point) for point in hull]


def _route_guidance(position_xy, forward_xy, waypoints, target_xy):
    """Use sourced approach points and observed pose for distance and steering."""
    points = [tuple(point[:2]) for point in waypoints] + [tuple(target_xy)]
    remaining_points = [point for point in points if
                        math.dist(tuple(position_xy), point) > 2.0 and
                        ((point[0] - position_xy[0]) * forward_xy[0] +
                         (point[1] - position_xy[1]) * forward_xy[1]) > 0.0]
    target_delta = (target_xy[0] - position_xy[0], target_xy[1] - position_xy[1])
    if math.hypot(*target_delta) > 2.0 and \
            target_delta[0] * forward_xy[0] + target_delta[1] * forward_xy[1] <= 0:
        raise ValueError('Original Native route overshot sourced stop target')
    aim = remaining_points[0] if remaining_points else tuple(target_xy)
    remaining = math.dist(tuple(position_xy), aim)
    remaining += sum(math.dist(a, b) for a, b in zip(remaining_points,
                                                     remaining_points[1:]))
    dx, dy = aim[0] - position_xy[0], aim[1] - position_xy[1]
    heading_error = math.atan2(forward_xy[0] * dy - forward_xy[1] * dx,
                               forward_xy[0] * dx + forward_xy[1] * dy)
    steer = max(-0.6, min(0.6, 0.7 * heading_error))
    return remaining, steer


def execute(config, output, device_source_path, host, port):
    # No CARLA connection occurs before all original device fields are present.
    check(config)
    require(device_source_path is not None, 'Original device source required for Native run')
    activity, condition = _identity(config['case_id'])
    source = _source(device_source_path, condition)
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original_world = snapshot(client)
    actors, sensors, encoders, encoder_logs = [], [], {}, {}
    packets = queue.Queue()
    try:
        require(world.get_map().name == source['map_name'], 'Device source map differs')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        require(len(spawns) > config['spawn_point_index'], 'Spawn point unavailable')
        start = spawns[config['spawn_point_index']].location
        if math.dist((start.x, start.y), source['approach_waypoints_xyz_m'][0][:2]) > 10.0:
            raise ValueError('Sourced approach does not join selected spawn')
        ego = world.try_spawn_actor(world.get_blueprint_library().find(config['vehicle_blueprint']),
                                    spawns[config['spawn_point_index']])
        require(ego is not None, 'Vehicle spawn occupied')
        actors.append(ego)
        for camera in config['cameras']:
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(camera['width']))
            blueprint.set_attribute('image_size_y', str(camera['height']))
            blueprint.set_attribute('fov', str(camera['fov_deg']))
            x, y, z = camera['location_xyz_m']
            pitch, yaw, roll = camera['rotation_pyr_deg']
            pose = carla.Transform(carla.Location(x=x, y=y, z=z),
                                   carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))
            sensor = world.spawn_actor(blueprint, pose, attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            encoder_logs[camera['name']] = (output / (camera['name'] + '.encoder.log')).open('x')
            encoders[camera['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f"{camera['width']}x{camera['height']}", '-r', '20',
                '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                str(output / (camera['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=encoder_logs[camera['name']])
            sensor.listen(lambda image, name=camera['name']: packets.put((name, image)))
        target_x, target_y, _ = source['target_xyz_m']
        with PipelineCapture(client, ego, output, config['case_id'],
                             required_observations=config.get('required_atoms', [])) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-stop-trace.jsonl').open('x', buffering=1) as trace:
            for index in range(FRAMES):
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(sum(v * v for v in _xyz(velocity)))
                forward = pose.get_forward_vector()
                remaining, steer = _route_guidance((pose.location.x, pose.location.y),
                                                    (forward.x, forward.y),
                                                    source['approach_waypoints_xyz_m'],
                                                    (target_x, target_y))
                control = command(index, remaining, speed)
                control['steer'] = steer
                control['hand_brake'] = activity == 'park' and control['phase'] == 'hold'
                ego.apply_control(carla.VehicleControl(throttle=control['throttle'],
                                                       brake=control['brake'],
                                                       steer=control['steer'],
                                                       hand_brake=control['hand_brake']))
                tick = world.tick()
                observed_pose = ego.get_transform()
                observed_velocity = ego.get_velocity()
                observed_speed = math.sqrt(sum(v * v for v in _xyz(observed_velocity)))
                observed_body = _body_footprint(
                    ego.bounding_box.get_world_vertices(observed_pose))
                seen = set()
                while len(seen) < len(VIEWS):
                    name, image = packets.get(timeout=15)
                    if image.frame != tick or name in seen:
                        continue
                    camera = next(c for c in config['cameras'] if c['name'] == name)
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        camera['height'], camera['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                    seen.add(name)
                capture.capture(tick, index / 20, extra={'video_frame': index,
                                                          'control_phase': control['phase']})
                frame_map.append(tick, index / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({'source_kind': 'original_native_observation',
                                        'video_frame': index, 'native_frame': tick,
                                        'time_s': index / 20, 'position_m': _xyz(observed_pose.location),
                                        'velocity_mps': _xyz(observed_velocity),
                                        'observed_speed_mps': observed_speed,
                                        'vehicle_footprint_map_m': observed_body,
                                        'target_xy_m': [target_x, target_y],
                                        'activity_mode_request': activity,
                                        'device_source_hashes': source['source_hashes'],
                                        'requested_control': control}) + '\n')
    finally:
        cleanup_errors = []
        for sensor in sensors:
            try:
                sensor.stop()
            except BaseException as error:
                cleanup_errors.append('sensor stop: ' + str(error))
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=120) != 0:
                    cleanup_errors.append('Original four-view encoder failed: ' + name)
            except BaseException as error:
                cleanup_errors.append('encoder close: ' + str(error))
            finally:
                encoder_logs[name].close()
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                cleanup_errors.append('actor destroy: ' + str(error))
        try:
            restore(client, original_world)
        except BaseException as error:
            cleanup_errors.append('world restore: ' + str(error))
        if cleanup_errors:
            raise RuntimeError('; '.join(cleanup_errors))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--device-source')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir is not None, '--output-dir required')
        execute(config, args.output_dir, args.device_source, args.host, args.port)
