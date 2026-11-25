"""Unselected school-bus source capture proposal for the frozen ice-cream cell."""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

from controller import control

PREFIX = 'training__C230241__NRS-484B-360-1__school_bus_driver__'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600
RATE = 20


def check(config):
    case = config.get('case_id')
    suffix = case[len(PREFIX):] if isinstance(case, str) and case.startswith(PREFIX) else ''
    if (suffix not in ('probe_a', 'probe_b') or config.get('law_id') != 'NRS-484B-360-1'
            or config.get('cell_id') != 'C230241' or config.get('actor') != 'school_bus_driver'
            or config.get('duration_s') != 30 or config.get('rate_hz') != RATE
            or config.get('requested_speed_mph') != (52 if suffix == 'probe_a' else 58)
            or config.get('cell_control') != 'ice_cream_truck'
            or config.get('school_bus_blueprint_confirmed') is not False
            or config.get('pupils_aboard_observed') is not False
            or config.get('legal_verdict') is not None):
        raise ValueError('Draft identity, control, or unverified source status changed')
    if type(config.get('spawn_point_index')) is not int or config['spawn_point_index'] < 0:
        raise ValueError('Spawn index required')
    cameras = config.get('cameras')
    if (not isinstance(cameras, list) or len(cameras) != 4
            or [c.get('name') for c in cameras] != list(VIEWS)):
        raise ValueError('Four named source cameras required')
    for camera in cameras:
        if ((camera.get('width'), camera.get('height')) != ((1920, 1080) if camera.get('name') == 'overview' else (1280, 720))
                or not isinstance(camera.get('pose'), list) or len(camera['pose']) != 6
                or not all(type(v) in (int, float) and math.isfinite(v) for v in camera['pose'])):
            raise ValueError('Original camera profile or pose missing')
    return {'case_id': case, 'frames': FRAMES, 'rate_hz': RATE,
            'cameras': list(VIEWS), 'selected': False, 'simulation_started': False,
            'pupils_aboard_observed': False, 'legal_verdict_claimed': False}


def resolve_assets(world):
    """Require verified exact classes; do not substitute a generic bus or van."""
    library = world.get_blueprint_library()
    bus = [b for b in library.filter('vehicle.*')
           if 'school' in b.id.lower() and 'bus' in b.id.lower()]
    truck = [b for b in library.filter('vehicle.*')
             if 'ice' in b.id.lower() and 'cream' in b.id.lower()]
    if len(bus) != 1 or len(truck) != 1:
        raise RuntimeError('Exact school-bus and ice-cream-truck blueprints require Native asset review')
    return bus[0], truck[0]


def camera_transform(carla, pose):
    x, y, z, pitch, yaw, roll = pose
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


def vec(v):
    return [v.x, v.y, v.z]


def execute(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output)
    client = carla.Client(host, port)
    client.set_timeout(15.0)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors = [], []
    packets = queue.Queue()
    errors, encoder_codes = [], {}
    restored, frames = {'restored': False}, 0
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        index = config['spawn_point_index']
        if index >= len(spawns):
            raise RuntimeError('Requested route spawn is unavailable')
        bus_bp, truck_bp = resolve_assets(world)
        bus = world.try_spawn_actor(bus_bp, spawns[index])
        if bus is None:
            raise RuntimeError('School-bus spawn occupied')
        actors.append(bus)
        truck_index = (index + config['ice_cream_spawn_offset']) % len(spawns)
        truck = world.try_spawn_actor(truck_bp, spawns[truck_index])
        if truck is None:
            raise RuntimeError('Ice-cream-truck spawn occupied')
        actors.append(truck)
        truck.apply_control(carla.VehicleControl(hand_brake=True))
        for camera in config['cameras']:
            name = camera['name']
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(camera['width']))
            bp.set_attribute('image_size_y', str(camera['height']))
            bp.set_attribute('fov', str(camera['fov_deg']))
            sensor = world.spawn_actor(bp, camera_transform(carla, camera['pose']), attach_to=bus)
            actors.append(sensor)
            sensors.append(sensor)
            (output / name).mkdir(exist_ok=False)
            sensor.listen(lambda image, view=name: packets.put((view, image)))
        (output / 'asset-selection.json').write_text(json.dumps({
            'school_bus_blueprint': bus_bp.id, 'ice_cream_truck_blueprint': truck_bp.id,
            'trip_purpose_confirmed': False, 'pupils_aboard_confirmed': False}, indent=2) + '\n')
        with PipelineCapture(client, bus, output, config['case_id'],
                             required_observations=['kin.position', 'kin.speed']) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'bus_motion.jsonl').open('x', buffering=1) as motion:
            for i in range(FRAMES):
                requested = control(config['case_id'][len(PREFIX):], vec(bus.get_velocity()))
                bus.apply_control(carla.VehicleControl(
                    throttle=requested['throttle'], brake=requested['brake'],
                    steer=requested['steer']))
                frame = world.tick()
                seen = set()
                while len(seen) < 4:
                    name, image = packets.get(timeout=15)
                    if image.frame != frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f'{i:06d}.png'))
                    seen.add(name)
                capture.capture(frame, i / RATE, extra={'video_frame': i})
                frame_map.append(frame, i / RATE,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                motion.write(json.dumps({'video_frame': i, 'native_frame': frame,
                    'source_kind': 'original_native_velocity',
                    'velocity_mps': vec(bus.get_velocity()),
                    'control_request': requested}) + '\n')
                frames += 1
        for name in VIEWS:
            command = ['ffmpeg', '-nostdin', '-v', 'error', '-framerate', str(RATE),
                       '-i', str(output / name / '%06d.png'), '-frames:v', str(FRAMES),
                       '-c:v', 'ffv1', str(output / (name + '.mkv'))]
            result = subprocess.run(command, timeout=300)
            encoder_codes[name] = result.returncode
            if result.returncode:
                raise RuntimeError('Camera encoder failed: ' + name)
    except BaseException as error:
        errors.append(f'{type(error).__name__}: {error}')
        raise
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
            restored = restore(client, original)
        except BaseException as error:
            errors.append(f'world restore: {error}')
        (output / 'native-run-status.json').write_text(json.dumps({
            'frames': frames, 'errors': errors, 'restoration': restored,
            'encoder_exit_codes': encoder_codes,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
    if errors:
        raise RuntimeError('; '.join(errors))
    seal_capture(output, frames=frames, restoration=restored, errors=errors,
                 encoder_exit_codes=encoder_codes,
                 context={'case_id': config['case_id'], 'pupils_aboard_confirmed': False,
                          'trip_purpose_confirmed': False, 'legal_verdict': None})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if args.output_dir is None:
            parser.error('--output-dir required')
        execute(config, args.output_dir, args.host, args.port)
