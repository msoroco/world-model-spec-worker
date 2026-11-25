"""Prospective original capture for the flashing-yellow-arrow turn cases.

Requested control and signal state are retained separately from observed motion
and pixels. Neither the signal's legal governance nor a participant's lawful
status is inferred by this runner.
"""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

from request import road
from branch_scenarios import BRANCHES, rows as branch_rows

PREFIX = 'training__C111603__NRS-484B-307-7a__motor_vehicle_driver__'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600
RATE = 20


def check(config):
    case = config.get('case_id')
    if (case not in tuple(PREFIX + key for key in BRANCHES)
            or config.get('selected_case_id') != case
            or config.get('cell_id') != 'C111603'
            or config.get('law_id') != 'NRS-484B-307-7a'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('candidate_id') not in ('primary', 'fallback1')
            or config.get('duration_s') != 30
            or config.get('rate_hz') != RATE
            or config.get('pedestrian_lawful_status') is not None
            or config.get('other_traffic_lawful_status') is not None
            or config.get('cautiousness_legal_judgment') is not None):
        raise ValueError('Exact flashing-arrow case identity or legal uncertainty differs')
    release = config.get('ego_release_frame')
    branch = case.removeprefix(PREFIX)
    if release != BRANCHES[branch]['release_frame']:
        raise ValueError('Statutory branch release differs')
    if config.get('requested_movement') != BRANCHES[branch]['movement']:
        raise ValueError('Statutory branch movement differs')
    if config.get('requested_concurrent_straight_indication') != BRANCHES[branch]['concurrent_straight']:
        raise ValueError('Concurrent indication request differs')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or [c.get('name') for c in cameras] != list(VIEWS):
        raise ValueError('Four named cameras required')
    for camera, size in zip(cameras, ((1920, 1080), (1280, 720),
                                     (1280, 720), (1280, 720))):
        if ([camera.get('width'), camera.get('height')] != list(size)
                or camera.get('fps') != RATE
                or len(camera.get('location_xyz_m', [])) != 3
                or len(camera.get('rotation_pyr_deg', [])) != 3
                or not all(isinstance(v, (int, float)) and math.isfinite(v)
                           for v in camera['location_xyz_m'] + camera['rotation_pyr_deg'])):
            raise ValueError('Camera size, rate or pose differs from source plan')
    for key in ('ego_throttle', 'other_throttle'):
        if type(config.get(key)) not in (int, float) or not 0 < config[key] < 0.7:
            raise ValueError('Invalid controller request: ' + key)
    return {'case_id': case, 'candidate_id': config['candidate_id'],
            'frames': FRAMES, 'rate_hz': RATE, 'cameras': list(VIEWS),
            'ego_release_frame': release, 'branch': branch, 'native_executed': False,
            'legal_verdict_claimed': False}


def control_for(config, frame, carla):
    if not 0 <= frame < FRAMES:
        raise ValueError('Frame outside required source window')
    release = config['ego_release_frame']
    if frame < release:
        ego = carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0)
    else:
        turn_frame = frame - release
        ego = carla.VehicleControl(throttle=config['ego_throttle'],
                                   steer=(0.30 if turn_frame < 85 else 0.0) if config['requested_movement'] == 'right' else 0.0,
                                   brake=0.0)
    other = carla.VehicleControl(throttle=config['other_throttle'],
                                 steer=0.0, brake=0.0)
    return ego, other


def actor_sample(actor):
    pose = actor.get_transform()
    return {'actor_id': str(actor.id),
            'position_m': [pose.location.x, pose.location.y, pose.location.z],
            'yaw_deg': pose.rotation.yaw,
            'velocity_mps': [actor.get_velocity().x, actor.get_velocity().y,
                             actor.get_velocity().z]}


def pose(carla, xyz, pyr):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pyr[0], yaw=pyr[1], roll=pyr[2]))


def execute(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output)
    if any(not (output / name).is_file()
           for name in ('config.json', 'construction.json', 'runner.py')):
        raise ValueError('Exact selected construction has not been materialized')
    client = carla.Client(host, port)
    client.set_timeout(15.0)
    original = snapshot(client)
    actors = []
    sensors = []
    packets = queue.Queue()
    errors = []
    encoders = {}
    restoration = {'restored': False}
    frames = 0
    failure = None
    try:
        world = client.generate_opendrive_world(road())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / RATE
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        ego_bp = blueprints.find('vehicle.tesla.model3')
        other_bp = blueprints.find('vehicle.audi.a2')
        ego = world.try_spawn_actor(ego_bp, pose(carla, [-1.75, -50, 0.5], [0, 90, 0]))
        other = world.try_spawn_actor(other_bp, pose(carla, [-30, 1.75, 0.5], [0, 0, 0]))
        if ego is None or other is None:
            raise RuntimeError('One or both required participant spawns failed')
        actors.extend((ego, other))
        lights = list(world.get_actors().filter('traffic.traffic_light*'))
        branch = config['case_id'].removeprefix(PREFIX)
        branch_request = branch_rows(branch)
        walker = None
        if branch.startswith('pedestrian_'):
            walker_bp = blueprints.find('walker.pedestrian.0001')
            walker = world.try_spawn_actor(walker_bp, pose(carla, [-5.0, -5.0, 0.5], [0, 0, 0]))
            if walker is None:
                raise RuntimeError('Required pedestrian spawn failed')
            actors.append(walker)
        (output / 'signal-inventory.json').write_text(json.dumps({
            'source_kind': 'original_native', 'requested_signal': 'flashing yellow right arrow',
            'actual_traffic_light_ids': [str(x.id) for x in lights],
            'governs_ego_verified': False, 'actual_arrow_pixels_reviewed': False},
            indent=2) + '\n')
        for camera in config['cameras']:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(camera['width']))
            bp.set_attribute('image_size_y', str(camera['height']))
            bp.set_attribute('fov', str(camera['fov_deg']))
            sensor = world.spawn_actor(bp, pose(carla, camera['location_xyz_m'],
                                                camera['rotation_pyr_deg']), attach_to=ego)
            sensors.append(sensor)
            actors.append(sensor)
            view = camera['name']
            (output / view).mkdir(exist_ok=False)
            sensor.listen(lambda image, name=view: packets.put((name, image)))
        with PipelineCapture(client, ego, output, config['case_id'],
                             required_observations=config.get('required_atoms', [])) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'turn-history.jsonl').open('x', buffering=1) as history:
            for index in range(FRAMES):
                ego_control, other_control = control_for(config, index, carla)
                ego.apply_control(ego_control)
                other.apply_control(other_control)
                if walker is not None:
                    walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=1.0, y=0.0, z=0.0), speed=2.0 if 170 <= index < 270 else 0.0, jump=False))
                for light in lights:
                    light.set_state(carla.TrafficLightState.Yellow if index % 20 < 10
                                    else carla.TrafficLightState.Off)
                    light.freeze(True)
                native_frame = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    view, image = packets.get(timeout=15)
                    if image.frame != native_frame or view in seen:
                        continue
                    image.save_to_disk(str(output / view / f'{index:06d}.png'))
                    seen.add(view)
                capture.capture(native_frame, index / RATE,
                                extra={'video_frame': index, 'requested_arrow_lit': index % 20 < 10})
                frame_map.append(native_frame, index / RATE,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                history.write(json.dumps({
                    'source_kind': 'original_native', 'native_frame': native_frame,
                    'frame': index, 'time_s': index / RATE,
                    'ego': actor_sample(ego), 'other_vehicle': actor_sample(other),
                    'requested_arrow_lit': index % 20 < 10,
                    'requested_concurrent_straight_indication': config['requested_concurrent_straight_indication'],
                    'requested_movement': config['requested_movement'],
                    'pedestrian': actor_sample(walker) if walker is not None else None,
                    'branch_request_sha256': config['branch_request_sha256'],
                    'actual_arrow_pixels_reviewed': False,
                    'other_traffic_lawful_status': None,
                    'pedestrian_lawful_status': None,
                    'cautiousness_legal_judgment': None}) + '\n')
                frames += 1
        for view in VIEWS:
            run = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-framerate',
                                  str(RATE), '-i', str(output / view / '%06d.png'),
                                  '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                                  str(output / (view + '.mkv'))], timeout=300)
            encoders[view] = run.returncode
            if run.returncode:
                raise RuntimeError(view + ' encoder failed')
        (output / 'arrow-context.json').write_text(json.dumps({
            'source_kind': 'original_native', 'case_id': config['case_id'],
            'camera_sources': {view: view + '.mkv' for view in VIEWS},
            'actual_arrow_pixels_reviewed': False, 'governs_ego_verified': False,
            'other_traffic_lawful_status_verified': False,
            'pedestrian_status_verified': False,
            'requested_concurrent_straight_indication': config['requested_concurrent_straight_indication'],
            'branch_request_sha256': config['branch_request_sha256'],
            'physical_cautiousness_verified': False}, indent=2) + '\n')
    except BaseException as error:
        failure = error
        errors.append(f'{type(error).__name__}: {error}')
    finally:
        for sensor in sensors:
            try:
                sensor.stop()
            except BaseException as error:
                errors.append(f'sensor stop: {error}')
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(f'actor destroy: {error}')
        try:
            restoration = restore(client, original)
        except BaseException as error:
            errors.append(f'world restore: {error}')
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': config['case_id'], 'frames': frames, 'errors': errors,
            'restoration': restoration, 'encoder_exit_codes': encoders,
            'capture_finished': frames == FRAMES and failure is None,
            'legal_verdict_claimed': False}, indent=2) + '\n')
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError('; '.join(errors))
    seal_capture(output, frames=frames, restoration=restoration, errors=errors,
                 encoder_exit_codes=encoders,
                 context={'case_id': config['case_id'], 'source': 'original Native CARLA',
                          'arrow_governance': None, 'traffic_lawfulness': None,
                          'cautiousness_legal_judgment': None})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        if args.output_dir is None:
            parser.error('--output-dir is required')
        execute(cfg, args.output_dir, args.host, args.port)
