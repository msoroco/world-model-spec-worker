"""Unselected 30-second Native crossing proposal; --check is CPU only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

HERE = Path(__file__).resolve().parent
RATE = 20
FRAMES = 600
CAMERAS = (
    {'name': 'overview', 'width': 1280, 'height': 720, 'xyz': (-10, 0, 9), 'yaw': 0, 'pitch': -55},
    {'name': 'entry_curb', 'width': 1280, 'height': 720, 'xyz': (-6, -4, 3), 'yaw': 30, 'pitch': -20},
    {'name': 'opposite_curb', 'width': 1280, 'height': 720, 'xyz': (6, 4, 3), 'yaw': 210, 'pitch': -20},
    {'name': 'route_profile', 'width': 1280, 'height': 720, 'xyz': (0, -10, 5), 'yaw': 90, 'pitch': -25},
)


def check(config):
    if (config['cell_id'], config['law_id'], config['actor']) != ('C230222', 'LVMC-11-30-050', 'pedestrian'):
        raise ValueError('Frozen assignment identity differs')
    if (config['duration_s'], config['rate_hz']) != (30, RATE):
        raise ValueError('Full crossing window differs')
    if config['case_id'] != config['selected_case_id']:
        raise ValueError('Exact case identity differs')
    if [(x['name'], x['width'], x['height']) for x in config['cameras']] != [
        (x['name'], x['width'], x['height']) for x in CAMERAS]:
        raise ValueError('Four source-camera contract differs')
    if config['condition'] not in ('right_angle', 'longer_diagonal'):
        raise ValueError('Unknown controlled path condition')
    if not (0 < config['walker_speed_mps'] <= 2.5):
        raise ValueError('Walker speed outside engineering bounds')
    if config['road_geometry_sha256'] != hashlib.sha256((HERE / 'road.xodr').read_bytes()).hexdigest():
        raise ValueError('Road source hash differs')
    return {'case_id': config['case_id'], 'frames': FRAMES, 'cameras': [x['name'] for x in CAMERAS],
            'condition': config['condition'], 'native_imported': False,
            'physical_result_claimed': False, 'legal_verdict_claimed': False}


def write_new(path, obj):
    with Path(path).open('x') as stream:
        json.dump(obj, stream, indent=2, allow_nan=False)
        stream.write('\n')


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use a newly materialized exact package directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    prior = client.get_world()
    state = snapshot(client)
    if state['settings'].synchronous_mode or any(
        actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for actor in prior.get_actors()
    ):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, encoders, logs, queues = [], {}, {}, {}
    capture = None
    changed = False
    error = None
    restored = None
    frames = 0
    try:
        world = client.generate_opendrive_world((HERE / 'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=True))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        library = world.get_blueprint_library()
        walkers = sorted(library.filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        if not walkers:
            raise RuntimeError('Native pedestrian blueprint unavailable')
        walker = world.try_spawn_actor(walkers[0], carla.Transform(
            carla.Location(x=-3.5, y=0, z=.5), carla.Rotation(yaw=0)))
        if walker is None:
            raise RuntimeError('Native walker spawn failed')
        owned.append(walker)
        for spec in CAMERAS:
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            x, y, z = spec['xyz']
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                carla.Rotation(yaw=spec['yaw'], pitch=spec['pitch'])))
            owned.append(sensor)
            queues[spec['name']] = queue.Queue()
            sensor.listen(queues[spec['name']].put)
            logs[spec['name']] = (output / (spec['name'] + '.encoder.log')).open('x')
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f"{spec['width']}x{spec['height']}", '-r', str(RATE),
                '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output / (spec['name'] + '.mkv'))], stdin=subprocess.PIPE,
                stderr=logs[spec['name']])
        capture = PipelineCapture(client, walker, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        target = (1.0, 0.0) if config['condition'] == 'right_angle' else (1.0, .4)
        magnitude = math.hypot(*target)
        direction = carla.Vector3D(x=target[0] / magnitude, y=target[1] / magnitude)
        with (output / 'route-samples.jsonl').open('x') as samples, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(FRAMES):
                observed_x = walker.get_transform().location.x
                walker.apply_control(carla.WalkerControl(direction=direction,
                    speed=config['walker_speed_mps'] if observed_x < 3.5 else 0))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = walker.get_transform().location
                observed = {'native_frame': frame, 'time_s': time_s,
                            'pedestrian_id': walker.id,
                            'pedestrian_xy_m': [pose.x, pose.y],
                            'pedestrian_speed_mps': math.hypot(walker.get_velocity().x, walker.get_velocity().y)}
                capture.capture(frame, time_s, extra={'route_proposal': observed})
                pixels = {}
                for spec in CAMERAS:
                    image = queues[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = queues[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Camera/Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    data = rgb.tobytes()
                    pixels[spec['name']] = hashlib.sha256(data).hexdigest()
                    encoders[spec['name']].stdin.write(data)
                observed['original_frame_sha256'] = pixels['route_profile']
                samples.write(json.dumps(observed, allow_nan=False) + '\n')
                frame_map.write(json.dumps({'video_frame': index, 'native_frame': frame,
                    'carla_frame': frame, 'time_s': time_s, 'source_rgb_sha256': pixels}) + '\n')
                frames += 1
        write_new(output / 'route-context.json', {
            'source_kind': 'native_observation', 'expected_frames': FRAMES,
            'origin_curb_xy_m': [[-3.5, -20], [-3.5, 20]],
            'opposite_curb_xy_m': [[3.5, -20], [3.5, 20]],
            'crosswalk_polygons_xy_m': [],
            'road_geometry_sha256': config['road_geometry_sha256'],
            'native_road_sha256': hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest(),
            'frame_map_sha256': hashlib.sha256((output / 'video_frames.jsonl').read_bytes()).hexdigest(),
            'crosswalk_status_requires_independent_map_and_pixel_audit': True})
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=False)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless camera encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, state)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        write_new(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'frames': frames, 'expected_frames': FRAMES,
            'restoration': restored, 'error': error, 'accepted': False,
            'legal_verdict_claimed': False})
    if error:
        raise RuntimeError('Native route attempt failed; inspect native-capture-report.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--config', type=Path, default=HERE / 'config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            raise ValueError('Explicit materialized package and owned Native endpoint required')
        execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
