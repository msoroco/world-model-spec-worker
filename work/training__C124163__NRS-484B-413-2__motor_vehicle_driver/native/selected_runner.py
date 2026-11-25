"""Exact NRS 484B.413(2) source capture proposal; no legal verdict."""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

from turn_capture_plan import CAMERAS, FRAMES, RATE_HZ, SIGNAL_REQUEST_M, plan

VIEWS = tuple(row[0] for row in CAMERAS)
CONDITIONS = tuple(SIGNAL_REQUEST_M)


def check(config):
    condition = config.get('condition')
    expected = plan(condition)
    if condition not in CONDITIONS or config.get('case_id', '').rsplit('__', 1)[-1] != condition:
        raise ValueError('Exact signal condition or case identity changed')
    for key in ('district_class', 'weather', 'requested_signal_distance_m',
                'rate_hz', 'frames', 'duration_s', 'maneuver', 'layout'):
        if config.get(key) != expected[key]:
            raise ValueError('Exact signal condition changed: ' + key)
    if (config.get('law_id') != 'NRS-484B-413-2' or config.get('cell_id') != 'C124163'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('legal_verdict') is not None):
        raise ValueError('Law, cell, actor or unverified status changed')
    if set(config.get('supported_case_ids', [])) != {
            config['case_id'].rsplit('__', 1)[0]+'__'+name for name in CONDITIONS}:
        raise ValueError('Exact selected case set changed')
    if type(config.get('spawn_point_index')) is not int or config['spawn_point_index'] < 0:
        raise ValueError('Spawn index missing')
    if (config.get('course_change_request_odometer_m') != 120.0 or
            config.get('signal_request_start_odometer_m') !=
            120.0 - expected['requested_signal_distance_m']):
        raise ValueError('Exact source distance request changed')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or [c.get('name') for c in cameras] != list(VIEWS):
        raise ValueError('Four canonical source cameras required')
    for camera in cameras:
        size = (1920, 1080) if camera['name'] == 'overview' else (1280, 720)
        if ((camera.get('width'), camera.get('height')) != size
                or not isinstance(camera.get('pose'), list) or len(camera['pose']) != 6
                or not camera.get('pose_strategy')
                or not all(type(x) in (int, float) and math.isfinite(x) for x in camera['pose'])):
            raise ValueError('Camera size or pose changed')
    return {'case_id': config['case_id'], 'frames': FRAMES, 'rate_hz': RATE_HZ,
            'cameras': list(VIEWS), 'legal_verdict_claimed': False,
            'simulation_started': False}


def _pose(carla, values):
    x, y, z, pitch, yaw, roll = values
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


def _distance(a, b):
    return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)


def execute(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output)
    if not output.is_dir() or not (output/'construction.json').is_file():
        raise ValueError('Expected materialized Native attempt is missing')
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors, errors, codes = [], [], [], {}
    packets = queue.Queue()
    restored, frames = {'restored': False}, 0
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/RATE_HZ
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        index = config['spawn_point_index']
        if index >= len(spawns):
            raise RuntimeError('Requested spawn point is unavailable')
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        ego = world.try_spawn_actor(blueprint, spawns[index])
        if ego is None or ego.type_id != 'vehicle.tesla.model3':
            raise RuntimeError('Subject spawn or blueprint readback failed')
        actors.append(ego)
        for camera in config['cameras']:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(camera['width']))
            bp.set_attribute('image_size_y', str(camera['height']))
            bp.set_attribute('fov', str(camera['fov_deg']))
            sensor = world.spawn_actor(bp, _pose(carla, camera['pose']), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output/camera['name']).mkdir()
            sensor.listen(lambda image, view=camera['name']: packets.put((view, image)))
        (output/'context-review.json').write_text(json.dumps({
            'district_class_requested': config['district_class'],
            'weather_requested': config['weather'],
            'district_class_originally_verified': False,
            'weather_originally_verified': False,
            'turn_route_originally_verified': False,
            'visible_signal_originally_verified': False,
            'legal_verdict': None}, indent=2)+'\n')
        previous = ego.get_location()
        odometer = 0.0
        with PipelineCapture(client, ego, output, config['case_id'],
                             required_observations=['kin.position', 'kin.speed']) as capture, \
                FrameMap(output/'video_frames.jsonl') as frame_map, \
                (output/'signal-source.jsonl').open('x', buffering=1) as samples:
            for i in range(FRAMES):
                # The request is only a stimulus; the post-tick readback is the source.
                requested_signal = odometer >= config['signal_request_start_odometer_m']
                requested_turn = odometer >= config['course_change_request_odometer_m']
                ego.set_light_state(carla.VehicleLightState.LeftBlinker if requested_signal
                                    else carla.VehicleLightState.NONE)
                ego.apply_control(carla.VehicleControl(
                    throttle=0.35, steer=0.22 if requested_turn else 0.0))
                frame = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    view, image = packets.get(timeout=15)
                    if image.frame != frame or view in seen:
                        continue
                    image.save_to_disk(str(output/view/f'{i:06d}.png'))
                    seen.add(view)
                location = ego.get_location()
                odometer += _distance(location, previous)
                previous = location
                snapshot_frame = world.get_snapshot().timestamp.elapsed_seconds
                capture.capture(frame, i/RATE_HZ, extra={'video_frame': i})
                frame_map.append(frame, i/RATE_HZ, native_elapsed_s=snapshot_frame,
                                 camera_native_frames={view: frame for view in VIEWS})
                lights = int(ego.get_light_state())
                sample = {'video_frame': i, 'native_frame': frame,
                          'source_kind': 'original_post_tick_native',
                          'time_s': snapshot_frame, 'odometer_native_m': odometer,
                          'left_blinker_state': bool(lights & int(carla.VehicleLightState.LeftBlinker)),
                          'signal_requested': requested_signal,
                          'course_change_requested': requested_turn,
                          'yaw_deg': ego.get_transform().rotation.yaw,
                          'position_m': [location.x, location.y, location.z],
                          'velocity_mps': [ego.get_velocity().x, ego.get_velocity().y,
                                           ego.get_velocity().z],
                          'signal_visible_pixels_reviewed': False}
                samples.write(json.dumps(sample, sort_keys=True)+'\n')
                frames += 1
        for view in VIEWS:
            command = ['ffmpeg', '-nostdin', '-v', 'error', '-framerate', str(RATE_HZ),
                       '-i', str(output/view/'%06d.png'), '-frames:v', str(FRAMES),
                       '-c:v', 'ffv1', str(output/(view+'.mkv'))]
            code = subprocess.run(command, timeout=300).returncode
            codes[view] = code
            if code:
                raise RuntimeError('Camera encode failed: '+view)
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
        (output/'native-run-status.json').write_text(json.dumps({
            'frames': frames, 'errors': errors, 'restoration': restored,
            'encoder_exit_codes': codes, 'physical_acceptance_claimed': False}, indent=2)+'\n')
    if errors:
        raise RuntimeError('; '.join(errors))
    seal_capture(output, frames=frames, restoration=restored, errors=errors,
                 encoder_exit_codes=codes,
                 context={'case_id': config['case_id'], 'legal_verdict': None,
                          'district_class_verified': False,
                          'visible_signal_pixels_verified': False})


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
            parser.error('--output-dir required')
        execute(cfg, args.output_dir, args.host, args.port)
