"""Proposed original C230222 capture; no driver-attention finding.

The runner records a 30-second source window. A controlled vehicle cannot
supply evidence of a human driver's interior attention state by itself.
"""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

PREFIX = 'training__C230222__LVMC-11-22-010__motor_vehicle_driver__'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600
RATE = 20


def check(config):
    case_id = config.get('case_id')
    if (case_id not in (PREFIX + 'reference', PREFIX + 'contrast')
            or config.get('selected_case_id') != case_id
            or config.get('cell_id') != 'C230222'
            or config.get('law_id') != 'LVMC-11-22-010'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('candidate_id') not in ('primary', 'fallback1', 'fallback2', 'fallback3')
            or config.get('duration_s') != 30
            or config.get('rate_hz') != RATE
            or config.get('vehicle_blueprint') != 'vehicle.tesla.model3'
            or config.get('required_atoms') != [
                'kin.position', 'kin.speed', 'kin.accel_longitudinal']
            or config.get('driver_attention_to_operation') is not None
            or config.get('legal_verdict') is not None
            or type(config.get('spawn_point_index')) is not int
            or config['spawn_point_index'] < 0):
        raise ValueError('Exact C230222 capture identity or duration differs')
    cameras = config.get('cameras')
    if (not isinstance(cameras, list) or len(cameras) != 4
            or [camera.get('name') for camera in cameras] != list(VIEWS)):
        raise ValueError('Four named source cameras required')
    for camera in cameras:
        if (type(camera.get('width')) is not int or camera['width'] < 16
                or type(camera.get('height')) is not int or camera['height'] < 16
                or type(camera.get('fov_deg')) not in (int, float)
                or not 1 <= camera['fov_deg'] <= 170
                or len(camera.get('location_xyz_m', [])) != 3
                or len(camera.get('rotation_pyr_deg', [])) != 3
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in camera['location_xyz_m'] + camera['rotation_pyr_deg'])):
            raise ValueError('Incomplete source-camera pose or optics')
    phases = config.get('control_phases')
    if not isinstance(phases, list) or not phases:
        raise ValueError('Full-window control schedule required')
    next_frame = 0
    for phase in phases:
        if (phase.get('first_frame') != next_frame
                or type(phase.get('last_frame')) is not int
                or not next_frame <= phase['last_frame'] < FRAMES
                or any(type(phase.get(key)) not in (int, float)
                       for key in ('throttle', 'steer', 'brake'))
                or not 0 <= phase['throttle'] <= 1
                or not -1 <= phase['steer'] <= 1
                or not 0 <= phase['brake'] <= 1):
            raise ValueError('Control schedule has a gap or invalid request')
        next_frame = phase['last_frame'] + 1
    if next_frame != FRAMES:
        raise ValueError('Control schedule does not reach frame 599')
    return {'case_id': case_id, 'frames': FRAMES, 'rate_hz': RATE,
            'camera_views': list(VIEWS), 'control_phases': len(phases),
            'carla_contacted': False, 'attention_observed': False,
            'source_kind': 'native_capture_proposal'}


def phase_at(config, frame):
    if not 0 <= frame < FRAMES:
        raise ValueError('Frame outside capture window')
    return next(phase for phase in config['control_phases']
                if phase['first_frame'] <= frame <= phase['last_frame'])


def transform(carla, camera):
    x, y, z = camera['location_xyz_m']
    pitch, yaw, roll = camera['rotation_pyr_deg']
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


def vector(value):
    return [value.x, value.y, value.z]


def execute(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    check(config)
    output = Path(output)
    if any(not (output / name).is_file()
           for name in ('config.json', 'construction.json', 'runner.py')):
        raise ValueError('Run from a materialized exact construction')
    client = carla.Client(host, port)
    client.set_timeout(15.0)
    world = client.get_world()
    original_world = snapshot(client)
    actors = []
    sensors = []
    packets = queue.Queue()
    errors = []
    encoder_exit_codes = {}
    restoration = {'restored': False}
    frames = 0
    failure = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / RATE
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        if len(spawns) <= config['spawn_point_index']:
            raise RuntimeError('Requested spawn unavailable')
        blueprint = world.get_blueprint_library().find(config['vehicle_blueprint'])
        ego = world.try_spawn_actor(blueprint, spawns[config['spawn_point_index']])
        if ego is None:
            raise RuntimeError('Requested spawn occupied')
        actors.append(ego)
        for camera in config['cameras']:
            view = camera['name']
            sensor_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            sensor_bp.set_attribute('image_size_x', str(camera['width']))
            sensor_bp.set_attribute('image_size_y', str(camera['height']))
            sensor_bp.set_attribute('fov', str(camera['fov_deg']))
            sensor = world.spawn_actor(sensor_bp, transform(carla, camera), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / view).mkdir(exist_ok=False)
            sensor.listen(lambda image, name=view: packets.put((name, image)))
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'case_id': config['case_id'], 'provenance_kind': 'native',
            'diagnostic_fixture': False, 'map_name': world.get_map().name,
            'vehicle_id': str(ego.id), 'driver_attention_observed': False}, indent=2) + '\n')
        with PipelineCapture(client, ego, output, config['case_id'],
                             required_observations=config.get('required_atoms', [])) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-ego-frames.jsonl').open('x', buffering=1) as motion:
            for index in range(FRAMES):
                phase = phase_at(config, index)
                ego.apply_control(carla.VehicleControl(
                    throttle=phase['throttle'], steer=phase['steer'], brake=phase['brake']))
                native_frame = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    view, image = packets.get(timeout=15)
                    if image.frame != native_frame or view in seen:
                        continue
                    image.save_to_disk(str(output / view / f'{index:06d}.png'))
                    seen.add(view)
                capture.capture(native_frame, index / RATE,
                                extra={'video_frame': index, 'control_phase': phase['name']})
                frame_map.append(native_frame, index / RATE,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                state = ego.get_transform()
                motion.write(json.dumps({
                    'source_kind': 'original_native', 'native_frame': native_frame,
                    'time_s': index / RATE, 'position_m': vector(state.location),
                    'velocity_mps': vector(ego.get_velocity()),
                    'acceleration_mps2': vector(ego.get_acceleration()),
                    'yaw_deg': state.rotation.yaw}) + '\n')
                frames += 1
        for view in VIEWS:
            encoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error',
                                      '-framerate', str(RATE), '-i',
                                      str(output / view / '%06d.png'),
                                      '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                                      str(output / (view + '.mkv'))], timeout=300)
            encoder_exit_codes[view] = encoded.returncode
            if encoded.returncode:
                raise RuntimeError(view + ' encoder failed')
        (output / 'native-driving-context.json').write_text(json.dumps({
            'source_kind': 'original_native',
            'camera_sources': {view: view + '.mkv' for view in VIEWS},
            'camera_pose_and_optics': config['cameras'],
            'map_name': world.get_map().name,
            'vehicle_id': str(ego.id),
            'driver_facing_pixels_reviewed': False,
            'driver_attention_to_operation': None,
            'legal_verdict': None}, indent=2) + '\n')
        from attention_observation import measure
        observation = measure(output)
        (output / 'attention-observation.json').write_text(
            json.dumps(observation, indent=2) + '\n')
    except BaseException as error:
        failure = error
        errors.append(f'{type(error).__name__}: {error}')
    finally:
        for sensor in sensors:
            try:
                sensor.stop()
            except BaseException as error:
                errors.append(f'sensor stop: {type(error).__name__}: {error}')
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(f'actor destroy: {type(error).__name__}: {error}')
        try:
            restoration = restore(client, original_world)
        except BaseException as error:
            errors.append(f'world restore: {type(error).__name__}: {error}')
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': config['case_id'], 'frames': frames, 'errors': errors,
            'restoration': restoration, 'encoder_exit_codes': encoder_exit_codes,
            'capture_finished': frames == FRAMES and failure is None,
            'attention_observed': False, 'acceptance_claimed': False}, indent=2) + '\n')
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError('; '.join(errors))
    try:
        seal_capture(output, frames=frames, restoration=restoration, errors=errors,
                     encoder_exit_codes=encoder_exit_codes,
                     context={'case_id': config['case_id'],
                              'source': 'original Native CARLA capture',
                              'driver_attention_to_operation': None,
                              'legal_verdict': None})
    except BaseException as error:
        errors.append(f'capture seal: {type(error).__name__}: {error}')
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': config['case_id'], 'frames': frames, 'errors': errors,
            'restoration': restoration, 'encoder_exit_codes': encoder_exit_codes,
            'capture_finished': False, 'attention_observed': False,
            'acceptance_claimed': False}, indent=2) + '\n')
        raise


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
            parser.error('--output-dir is required for Native capture')
        execute(config, args.output_dir, args.host, args.port)
