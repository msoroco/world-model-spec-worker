"""C229597 Native capture proposal and CPU configuration check.

The controller creates an observable acceleration episode. Whether it is an
exhibition under the statute requires independent source and context review.
"""
import argparse
import json
import queue
import subprocess
from pathlib import Path

PREFIX = 'training__C229597__LVMC-11-16-090-A__motor_vehicle_driver__'
THROTTLES = {
    'reference': (0.28, 0.75, 0.92, 0.20),
    'contrast': (0.28, 0.28, 0.28, 0.20),
}
SPAWNS = {'primary': 0, 'fallback1': 1, 'fallback2': 2, 'fallback3': 3}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600
HZ = 20


def check(config):
    case = config.get('case')
    candidate = config.get('candidate_id')
    if (case not in THROTTLES
            or config.get('case_id') != PREFIX + case
            or config.get('selected_case_id') != PREFIX + case
            or config.get('cell_id') != 'C229597'
            or config.get('law_id') != 'LVMC-11-16-090-A'
            or config.get('actor') != 'motor_vehicle_driver'
            or candidate not in SPAWNS
            or config.get('spawn_point_index') != SPAWNS.get(candidate)
            or config.get('rate_hz') != HZ
            or config.get('duration_s') != 30
            or config.get('vehicle_blueprint') != 'vehicle.tesla.model3'):
        raise ValueError('Exact case or 30-second vehicle contract differs')
    phases = config.get('control_phases')
    expected = [(0, 159, THROTTLES[case][0]),
                (160, 319, THROTTLES[case][1]),
                (320, 439, THROTTLES[case][2]),
                (440, 599, THROTTLES[case][3])]
    if (not isinstance(phases, list) or len(phases) != len(expected)
            or [(p.get('first_frame'), p.get('last_frame'), p.get('throttle'))
                for p in phases] != expected
            or any(p.get('steer') != 0.0 or p.get('brake') != 0.0 for p in phases)):
        raise ValueError('Approach, acceleration and departure controls differ')
    cameras = config.get('cameras')
    if (not isinstance(cameras, list)
            or [c.get('name') for c in cameras] != list(VIEWS)
            or any(c.get('width') != 1280 or c.get('height') != 720
                   or c.get('fov_deg') != 90 for c in cameras)):
        raise ValueError('Four synchronized source cameras required')
    return {'case_id': PREFIX + case, 'candidate_id': candidate,
            'frames': FRAMES, 'rate_hz': HZ,
            'camera_views': list(VIEWS), 'phase_boundaries': [0, 160, 320, 440, 600],
            'carla_contacted': False, 'source_kind': 'native_proposal',
            'highway_status_verified': False, 'exhibition_accepted': False}


def phase_at(config, frame):
    if not 0 <= frame < FRAMES:
        raise ValueError('Frame outside capture window')
    return next(p for p in config['control_phases']
                if p['first_frame'] <= frame <= p['last_frame'])


def camera_transform(carla, name):
    poses = {
        'overview': ((-12, 0, 12), (-35, 0, 0)),
        'approach': ((8, -12, 5), (-10, 35, 0)),
        'reference_corner': ((-8, 10, 5), (-10, -35, 0)),
        'driver_reference': ((0.4, 0, 1.5), (0, 0, 0)),
    }
    xyz, pyr = poses[name]
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pyr[0], yaw=pyr[1], roll=pyr[2]))


def execute(config, output, host, port):
    import carla

    check(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = carla.Client(host, port)
    client.set_timeout(15.0)
    world = client.get_world()
    old_settings = world.get_settings()
    actors = []
    sensors = {}
    packets = queue.Queue()
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / HZ
        world.apply_settings(settings)
        spawn = world.get_map().get_spawn_points()
        if len(spawn) <= config['spawn_point_index']:
            raise RuntimeError('Requested route spawn unavailable')
        blueprint = world.get_blueprint_library().find(config['vehicle_blueprint'])
        ego = world.try_spawn_actor(blueprint, spawn[config['spawn_point_index']])
        if ego is None:
            raise RuntimeError('Requested route spawn occupied')
        actors.append(ego)
        for camera in config['cameras']:
            name = camera['name']
            sensor_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            sensor_bp.set_attribute('image_size_x', str(camera['width']))
            sensor_bp.set_attribute('image_size_y', str(camera['height']))
            sensor_bp.set_attribute('fov', str(camera['fov_deg']))
            sensor = world.spawn_actor(sensor_bp, camera_transform(carla, name),
                                       attach_to=ego)
            actors.append(sensor)
            sensors[name] = sensor
            (output / name).mkdir()
            sensor.listen(lambda image, view=name: packets.put((view, image)))
        metadata = {'case_id': config['case_id'],
                    'candidate_id': config['candidate_id'],
                    'frames': FRAMES, 'rate_hz': HZ,
                    'map_name': world.get_map().name,
                    'vehicle_id': str(ego.id), 'camera_views': list(VIEWS),
                    'highway_status_verified': False,
                    'exhibition_accepted': False}
        (output / 'capture-manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'case_id': config['case_id'], 'provenance_kind': 'native',
            'diagnostic_fixture': False, 'map_name': world.get_map().name,
            'vehicle_id': str(ego.id), 'highway_status_verified': False,
            'exhibition_accepted': False}, indent=2) + '\n')
        with (output / 'trace.jsonl').open('w') as trace, \
                (output / 'video_frames.jsonl').open('w') as frame_map:
            for index in range(FRAMES):
                phase = phase_at(config, index)
                ego.apply_control(carla.VehicleControl(throttle=phase['throttle'],
                                                       steer=phase['steer'],
                                                       brake=phase['brake']))
                frame_id = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    view, image = packets.get(timeout=15)
                    if image.frame != frame_id or view in seen:
                        continue
                    image.save_to_disk(str(output / view / f'{index:06d}.png'))
                    seen.add(view)
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                acceleration = ego.get_acceleration()
                timestamp = world.get_snapshot().timestamp.elapsed_seconds
                mapping = {'video_frame': index, 'carla_frame': frame_id,
                           'native_frame': frame_id, 'time_s': index / HZ,
                           'native_elapsed_s': timestamp}
                frame_map.write(json.dumps(mapping, allow_nan=False) + '\n')
                row = {'frame': frame_id, 'video_frame': index,
                       'native_frame': frame_id,
                       'time_s': index / HZ,
                       'location_m': [pose.location.x, pose.location.y, pose.location.z],
                       'position_m': [pose.location.x, pose.location.y, pose.location.z],
                       'rotation_deg': [pose.rotation.pitch, pose.rotation.yaw,
                                        pose.rotation.roll],
                       'velocity_mps': [velocity.x, velocity.y, velocity.z],
                       'acceleration_mps2': [acceleration.x, acceleration.y,
                                            acceleration.z],
                       'vehicle_id': str(ego.id), 'phase': phase['name']}
                trace.write(json.dumps(row, allow_nan=False) + '\n')
        for view in VIEWS:
            subprocess.run(('ffmpeg', '-v', 'error', '-framerate', str(HZ),
                            '-i', str(output / view / '%06d.png'),
                            '-c:v', 'ffv1', str(output / (view + '.mkv'))),
                           check=True, timeout=300)
    finally:
        for sensor in sensors.values():
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(old_settings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if args.output is None:
            parser.error('--output is required for Native capture')
        execute(config, args.output, args.host, args.port)
