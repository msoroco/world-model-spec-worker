"""C230241 motorcycle lighting capture proposal and CPU contract check.

Native capture retains original light state, motion and four camera streams.
It does not infer visible distance or a legal outcome from requested lighting.
"""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

PREFIX = 'training__C230241__LVMC-11-38-120-B__motorcycle_or_moped_operator__'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
RATE = 20
FRAMES = 600


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(config):
    case_id = config.get('case_id')
    require(case_id == PREFIX + 'reference' and
            config.get('selected_case_id') == case_id and
            config.get('cell_id') == 'C230241' and
            config.get('law_id') == 'LVMC-11-38-120-B' and
            config.get('actor') == 'motorcycle_or_moped_operator' and
            config.get('frozen_cell') == {'layout': 'road', 'maneuver': 'travel',
                                          'control': 'ice_cream_truck'} and
            config.get('candidate_id') in ('primary', 'fallback1',
                                           'fallback2', 'fallback3') and
            config.get('rate_hz') == RATE and config.get('duration_s') == 30 and
            config.get('vehicle_blueprint') == 'vehicle.harley-davidson.low_rider' and
            config.get('vendor_blueprint') == 'vehicle.volkswagen.t2' and
            type(config.get('vendor_spawn_point_index')) is int and
            config['vendor_spawn_point_index'] > config['spawn_point_index'] and
            config.get('requested_light_state') == 'LowBeam|Position' and
            config.get('physical_visibility_verified') is False and
            config.get('legal_verdict') is None,
            'Exact C230241 identity, vehicle, light or duration differs')
    require(type(config.get('spawn_point_index')) is int and
            config['spawn_point_index'] >= 0, 'Spawn point index invalid')
    cameras = config.get('cameras')
    require(isinstance(cameras, list) and len(cameras) == 4 and
            tuple(item.get('name') for item in cameras) == VIEWS,
            'Four named source cameras required')
    for camera in cameras:
        require(type(camera.get('width')) is int and camera['width'] >= 16 and
                type(camera.get('height')) is int and camera['height'] >= 16 and
                camera.get('fps') == RATE and
                type(camera.get('fov_deg')) in (int, float) and
                1 <= camera['fov_deg'] <= 170 and
                len(camera.get('location_xyz_m', [])) == 3 and
                len(camera.get('rotation_pyr_deg', [])) == 3 and
                all(type(value) in (int, float) and math.isfinite(value)
                    for value in camera['location_xyz_m'] +
                    camera['rotation_pyr_deg']), 'Camera pose or optics invalid')
    phases = config.get('control_phases')
    require(isinstance(phases, list) and bool(phases),
            'Complete controller schedule required')
    next_frame = 0
    for phase in phases:
        require(phase.get('first_frame') == next_frame and
                type(phase.get('last_frame')) is int and
                next_frame <= phase['last_frame'] < FRAMES and
                all(type(phase.get(key)) in (int, float)
                    for key in ('throttle', 'steer', 'brake')) and
                0 <= phase['throttle'] <= 1 and -1 <= phase['steer'] <= 1 and
                0 <= phase['brake'] <= 1,
                'Controller schedule has a gap or invalid request')
        next_frame = phase['last_frame'] + 1
    require(next_frame == FRAMES, 'Controller ends before frame 599')
    return {'case_id': case_id, 'candidate_id': config['candidate_id'],
            'frames': FRAMES, 'rate_hz': RATE,
            'source_views': list(VIEWS), 'controller_phases': len(phases),
            'carla_contacted': False, 'physical_visibility_verified': False,
            'legal_verdict': None}


def phase_at(config, frame):
    require(0 <= frame < FRAMES, 'Frame outside capture window')
    return next(phase for phase in config['control_phases']
                if phase['first_frame'] <= frame <= phase['last_frame'])


def _transform(carla, camera):
    x, y, z = camera['location_xyz_m']
    pitch, yaw, roll = camera['rotation_pyr_deg']
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


def _xyz(vector):
    return [vector.x, vector.y, vector.z]


def execute(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    check(config)
    output = Path(output)
    require(all((output / name).is_file() for name in
                ('config.json', 'construction.json', 'runner.py')),
            'Run from a materialized exact construction')
    client = carla.Client(host, port)
    client.set_timeout(15.0)
    world = client.get_world()
    original_world = snapshot(client)
    actors, sensors, errors = [], [], []
    packets = queue.Queue()
    encoder_codes = {}
    restoration = {'restored': False}
    frames = 0
    failure = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        weather = world.get_weather()
        weather.sun_altitude_angle = -8
        weather.precipitation = 0
        world.set_weather(weather)
        spawns = world.get_map().get_spawn_points()
        require(len(spawns) > config['spawn_point_index'],
                'Requested spawn unavailable')
        blueprint = world.get_blueprint_library().find(config['vehicle_blueprint'])
        ego = world.try_spawn_actor(blueprint, spawns[config['spawn_point_index']])
        require(ego is not None, 'Requested motorcycle spawn occupied')
        actors.append(ego)
        require(len(spawns) > config['vendor_spawn_point_index'],
                'Requested vendor spawn unavailable')
        vendor_bp = world.get_blueprint_library().find(config['vendor_blueprint'])
        if vendor_bp.has_attribute('role_name'):
            vendor_bp.set_attribute('role_name', 'ice_cream_truck_candidate')
        vendor = world.try_spawn_actor(vendor_bp,
                                       spawns[config['vendor_spawn_point_index']])
        require(vendor is not None, 'Requested vendor vehicle spawn occupied')
        actors.append(vendor)
        vendor.set_simulate_physics(False)
        lights = carla.VehicleLightState.LowBeam | carla.VehicleLightState.Position
        ego.set_light_state(carla.VehicleLightState(lights))
        for camera in config['cameras']:
            view = camera['name']
            sensor_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            sensor_bp.set_attribute('image_size_x', str(camera['width']))
            sensor_bp.set_attribute('image_size_y', str(camera['height']))
            sensor_bp.set_attribute('fov', str(camera['fov_deg']))
            sensor = world.spawn_actor(sensor_bp, _transform(carla, camera),
                                       attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / view).mkdir(exist_ok=False)
            sensor.listen(lambda image, name=view: packets.put((name, image)))
        with PipelineCapture(client, ego, output, config['case_id'],
                             required_observations=config.get('required_atoms', [])) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-lighting-frames.jsonl').open('x', buffering=1) as motion:
            for index in range(FRAMES):
                phase = phase_at(config, index)
                ego.apply_control(carla.VehicleControl(
                    throttle=phase['throttle'], steer=phase['steer'],
                    brake=phase['brake']))
                native_frame = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    view, image = packets.get(timeout=15)
                    if image.frame != native_frame or view in seen:
                        continue
                    image.save_to_disk(str(output / view / f'{index:06d}.png'))
                    seen.add(view)
                capture.capture(native_frame, index / RATE,
                                extra={'video_frame': index,
                                       'control_phase': phase['name']})
                frame_map.append(native_frame, index / RATE,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                state = ego.get_transform()
                motion.write(json.dumps({
                    'source_kind': 'original_native_observation',
                    'video_frame': index, 'native_frame': native_frame,
                    'time_s': index / RATE, 'position_m': _xyz(state.location),
                    'velocity_mps': _xyz(ego.get_velocity()),
                    'yaw_deg': state.rotation.yaw,
                    'light_state_observed': int(ego.get_light_state()),
                    'light_state_requested': 'LowBeam|Position'}) + '\n')
                frames += 1
        for view in VIEWS:
            encoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error',
                                      '-framerate', str(RATE), '-i',
                                      str(output / view / '%06d.png'),
                                      '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                                      str(output / (view + '.mkv'))], timeout=300)
            encoder_codes[view] = encoded.returncode
            require(encoded.returncode == 0, view + ' encoder failed')
        inputs = [item for view in VIEWS for item in
                  ('-i', str(output / (view + '.mkv')))]
        layout = ('[0:v]scale=960:540[v0];[1:v]scale=960:540[v1];'
                  '[2:v]scale=960:540[v2];[3:v]scale=960:540[v3];'
                  '[v0][v1][v2][v3]xstack=inputs=4:'
                  'layout=0_0|960_0|0_540|960_540[out]')
        composed = subprocess.run(
            ['ffmpeg', '-nostdin', '-v', 'error', *inputs,
             '-filter_complex', layout, '-map', '[out]',
             '-frames:v', str(FRAMES), '-c:v', 'ffv1',
             str(output / 'raw.mkv')], timeout=900)
        encoder_codes['raw'] = composed.returncode
        require(composed.returncode == 0, 'Composed primary video encoder failed')
        (output / 'native-lighting-context.json').write_text(json.dumps({
            'source_kind': 'original_native_observation',
            'vehicle_blueprint': config['vehicle_blueprint'],
            'vendor_blueprint': config['vendor_blueprint'],
            'vendor_id': str(vendor.id),
            'vendor_physical_identity_verified': False,
            'map_name': world.get_map().name,
            'camera_sources': {view: view + '.mkv' for view in VIEWS},
            'camera_pose_and_optics': config['cameras'],
            'sun_altitude_angle_requested': -8,
            'sunset_utc_s': None, 'next_sunrise_utc_s': None,
            'range_calibration_source': None,
            'visibility_review_source': None,
            'physical_visibility_verified': False,
            'legal_verdict': None}, indent=2) + '\n')
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
            'restoration': restoration, 'encoder_exit_codes': encoder_codes,
            'capture_finished': frames == FRAMES and failure is None,
            'physical_visibility_verified': False,
            'acceptance_claimed': False}, indent=2) + '\n')
    if failure is not None:
        raise failure
    require(not errors, '; '.join(errors))
    seal_capture(output, frames=frames, restoration=restoration,
                 errors=errors, encoder_exit_codes=encoder_codes,
                 context={'case_id': config['case_id'],
                          'source': 'original Native CARLA capture',
                          'physical_visibility_verified': False,
                          'legal_verdict': None})


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
        require(args.output_dir is not None, '--output-dir required')
        execute(config, args.output_dir, args.host, args.port)
