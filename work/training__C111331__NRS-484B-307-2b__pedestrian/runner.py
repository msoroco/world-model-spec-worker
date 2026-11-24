"""C111331 Native pedestrian crossing attempt; --check is CPU-only.

The OpenDRIVE signal objects and requested phases are construction targets.
Actual display pixels, governing direction and highway status need saved review.
"""

import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import traceback

from construction import VIEWS, check_map, proposal
from signals import (resolve as resolve_signal_heads, sample as sample_signal_heads,
                     configure as configure_signal_heads)

HERE = Path(__file__).resolve().parent


def check(config):
    plan = proposal(config['case_suffix'])
    if config['case_id'] != plan['case_id'] or \
            config['selected_case_id'] != plan['case_id'] or \
            config['cell_id'] != 'C111331' or \
            config['law_id'] != 'NRS-484B-307-2b' or \
            config['actor'] != 'pedestrian':
        raise ValueError('Frozen exact case identity differs')
    if config['duration_s'] != 30 or config['rate_hz'] != 20 or \
            [(c['name'], c['width'], c['height']) for c in config['cameras']] != [(c['name'], c['width'], c['height']) for c in plan['cameras']]:
        raise ValueError('Thirty-second four-camera contract differs')
    if config['requested_pedestrian_indication'] != plan['requested_pedestrian_indication']:
        raise ValueError('Only planned contrary-device state may differ')
    return {'case_id': plan['case_id'], 'geometry': check_map(),
            'frames': 600, 'camera_views': [n for n, _, _ in VIEWS],
            'native_executed': False, 'physical_signal_verified': False,
            'legal_verdict': None}


def _write_new(path, data):
    with Path(path).open('x') as out:
        json.dump(data, out, indent=2, allow_nan=False)
        out.write('\n')


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use the exact newly materialized candidate directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    original = snapshot(client)
    if original['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in prior.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, streams, encoders, encoder_logs = [], {}, {}, {}
    capture = None
    changed = False
    restored = None
    error = None
    frames = 0
    try:
        world = client.generate_opendrive_world((HERE / 'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=True))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        library = world.get_blueprint_library()
        heads = resolve_signal_heads(world.get_actors())
        configure_signal_heads(heads, config['requested_pedestrian_indication'], carla)
        walkers = sorted(library.filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        if not walkers:
            raise RuntimeError('No Native pedestrian blueprint available')
        walker = world.try_spawn_actor(walkers[0], carla.Transform(
            carla.Location(x=0, y=-5, z=.5), carla.Rotation(yaw=90)))
        if walker is None:
            raise RuntimeError('Native pedestrian spawn failed')
        owned.append(walker)
        camera_poses = {
            'overview': (-10, -10, 9, 45, -35),
            'approach': (0, -8, 4, 90, -18),
            'reference_corner': (-4, -4, 3, 45, -22),
            'driver_reference': (1, -5, 2, 90, -8),
        }
        for name, width, height in VIEWS:
            x, y, z, yaw, pitch = camera_poses[name]
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw, pitch=pitch)))
            owned.append(sensor)
            streams[name] = queue.Queue()
            sensor.listen(streams[name].put)
            encoder_logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=encoder_logs[name])
        capture = PipelineCapture(client, walker, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=0, y=1),
                                                speed=1.05))
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'c111331-native-samples.jsonl').open('x') as samples, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(600):
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = walker.get_transform()
                traffic = sorted((actor for actor in world.get_actors()
                                  if actor.type_id.startswith('traffic.traffic_light')),
                                 key=lambda actor: actor.id)
                observed = sample_signal_heads(heads)
                source = {'video_frame': index, 'native_frame': frame,
                          'time_s': time_s, 'pedestrian_id': walker.id,
                          'pedestrian_xy_m': [pose.location.x, pose.location.y],
                          'native_traffic_lights': [
                              {'actor_id': light.id, 'state': str(light.get_state()),
                               'location_xyz_m': [light.get_location().x,
                                                  light.get_location().y,
                                                  light.get_location().z]}
                              for light in traffic],
                          'traffic_head_id': config['traffic_head_id'],
                          'pedestrian_head_id': config['pedestrian_head_id'],
                          'observed_traffic_signal': observed['traffic'],
                          'observed_pedestrian_signal': observed['pedestrian'],
                          'requested_pedestrian_indication': config['requested_pedestrian_indication'],
                          'governance_confirmed': False}
                capture.capture(frame, time_s, extra={'c111331_source': source})
                pixels = {}
                for name, width, height in VIEWS:
                    image = streams[name].get(timeout=30)
                    while image.frame < frame:
                        image = streams[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera and Native frame differ')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1].tobytes()
                    pixels[name] = hashlib.sha256(rgb).hexdigest()
                    encoders[name].stdin.write(rgb)
                samples.write(json.dumps(source, allow_nan=False) + '\n')
                frame_map.write(json.dumps({'video_frame': index,
                    'native_frame': frame, 'carla_frame': frame, 'time_s': time_s,
                    'source_rgb_sha256': pixels}, allow_nan=False) + '\n')
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try: capture.close(confirmed=error is None)
            except BaseException as exc: error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        if changed:
            try: restored = restore(client, original)
            except BaseException as exc: error = error or {'world_restore_error': str(exc)}
        _write_new(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'frames': frames, 'expected_frames': 600,
            'restoration': restored, 'error': error, 'accepted': False,
            'physical_signal_verified': False,
            'device_governance_verified': False})
    if error:
        raise RuntimeError('Native crossing attempt failed; see native-capture-report.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads((HERE / 'config.json').read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            raise ValueError('Owned Native endpoint and materialized output required')
        execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
