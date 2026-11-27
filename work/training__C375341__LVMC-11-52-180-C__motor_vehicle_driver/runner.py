"""Source-gated Native alley parking clip; the hour ledger is independent original evidence."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C375341__LVMC-11-52-180-C__motor_vehicle_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUESTS = {'probe_1': 1500, 'probe_at_30': 1800, 'probe_2': 2100}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(config):
    suffix = config['case_id'].rsplit('__', 1)[-1]
    require(config['case_id'] == ASSIGNMENT + '__' + suffix and suffix in REQUESTS and
            config['law_id'] == 'LVMC-11-52-180-C' and config['cell_id'] == 'C375341' and
            config['actor'] == 'motor_vehicle_driver', 'exact alley assignment changed')
    require(config['frozen_cell'] == {'layout': 'alley', 'maneuver': 'park', 'control': 'alley_entrance'},
            'frozen alley cell changed')
    require(config['requested_parked_seconds_in_rolling_hour'] == REQUESTS[suffix],
            'requested hour target changed')
    require(config['rate_hz'] == 20 and config['duration_s'] == 30 and config['frames'] == 600,
            '30-second Native clip contract missing')
    require(tuple(c['name'] for c in config['cameras']) == VIEWS and
            all(c['fps'] == 20 and c['width'] >= 1280 and c['height'] >= 720 for c in config['cameras']),
            'four-camera Native source contract missing')
    require(config.get('legal_verdict') is None and not config.get('physical_completion'),
            'premature physical or legal outcome')
    return {'case_id': config['case_id'], 'frames': 600, 'carla_contacted': False,
            'requested_hour_seconds': REQUESTS[suffix], 'observed_hour_seconds': None}


def inside_polygon(x, y, vertices):
    inside = False
    previous = len(vertices) - 1
    for index, (vx, vy) in enumerate(vertices):
        px, py = vertices[previous]
        if ((vy > y) != (py > y)) and x < (px - vx) * (y - vy) / (py - vy) + vx:
            inside = not inside
        previous = index
    return inside


def read_original(context_path, ledger_path):
    require(context_path and ledger_path, 'Original alley context and hour ledger required')
    context = json.loads(Path(context_path).read_text())
    ledger = json.loads(Path(ledger_path).read_text())
    require(context.get('assignment_id') == ASSIGNMENT and
            context.get('source_kind') == 'original_native_alley_parking_ledger' and
            context.get('fixed_cell') == {'layout': 'alley', 'maneuver': 'park', 'control': 'alley_entrance'},
            'Original alley context identity missing')
    require(context.get('map_name') and context.get('vehicle_blueprint') and
            len(context.get('spawn_xyz_yaw_deg', [])) == 4,
            'Original alley map/spawn source missing')
    polygon = context.get('alley_polygon_xy_m', [])
    require(len(polygon) >= 3 and all(len(v) == 2 and all(type(c) in (int, float) and math.isfinite(c) for c in v) for v in polygon),
            'Surveyed alley boundary missing')
    require(context.get('alley_status') == 'source_surveyed_alley' and
            context.get('otherwise_lawful_review') == 'independently_reviewed',
            'Original alley/lawful prerequisite not reviewed')
    require(context.get('parking_ledger_sha256') == sha(ledger_path),
            'Original hour ledger source hash changed')
    for key in ('native_map_sha256', 'alley_boundary_sha256', 'vehicle_identity_sha256',
                'civil_time_source_sha256', 'lawful_parking_review_sha256'):
        value = context.get(key)
        require(isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
                'Missing original source hash: ' + key)
        document = context.get('source_documents', {}).get(key)
        require(isinstance(document, str) and document.startswith('original-') and
                '/' not in document and '\\' not in document,
                'Missing original source document: ' + key)
        require(sha(Path(context_path).parent / document) == value,
                'Original source document hash changed: ' + key)
    require(set(context.get('camera_poses', {})) == set(VIEWS) and
            all(len(context['camera_poses'][name].get('location_xyz_m', [])) == 3 and
                len(context['camera_poses'][name].get('rotation_pyr_deg', [])) == 3 for name in VIEWS),
            'Original alley camera pose survey missing')
    require(ledger.get('span_end_s', 0) - ledger.get('span_start_s', 0) >= 3600 and
            ledger.get('capture_start_s') is not None and context.get('vehicle_id'),
            'Original one-hour civil ledger missing')
    return context, ledger


def execute(config, output_dir, context_path, ledger_path, host, port):
    check(config)
    context, ledger = read_original(context_path, ledger_path)
    require('.runtime-work' in os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', ''),
            'set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    repo = ROOT.parents[2]
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    sys.path.insert(1, str(repo / 'runtime/python'))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot
    output = Path(output_dir)
    require(output.is_dir(), 'materialized Native output required')
    (output / 'original_alley_context.json').write_bytes(Path(context_path).read_bytes())
    (output / 'original_parking_ledger.json').write_bytes(Path(ledger_path).read_bytes())
    for document in context['source_documents'].values():
        (output / document).write_bytes((Path(context_path).parent / document).read_bytes())
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors, encoders, codes = [], [], {}, {}
    images = queue.Queue()
    finished = False
    try:
        require(world.get_map().name == context['map_name'], 'Original alley map differs')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        bp = library.find(context['vehicle_blueprint'])
        require(bp is not None, 'Vehicle blueprint unavailable')
        x, y, z, yaw = context['spawn_xyz_yaw_deg']
        vehicle = world.try_spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
        require(vehicle is not None, 'Surveyed alley spawn occupied')
        actors.append(vehicle)
        for camera in config['cameras']:
            cb = library.find('sensor.camera.rgb')
            cb.set_attribute('image_size_x', str(camera['width']))
            cb.set_attribute('image_size_y', str(camera['height']))
            cb.set_attribute('fov', str(camera['fov_deg']))
            source_pose = context['camera_poses'][camera['name']]
            cx, cy, cz = source_pose['location_xyz_m']
            pitch, cyaw, roll = source_pose['rotation_pyr_deg']
            sensor = world.spawn_actor(cb, carla.Transform(carla.Location(x=cx, y=cy, z=cz),
                                       carla.Rotation(pitch=pitch, yaw=cyaw, roll=roll)),
                                       attach_to=vehicle if camera['name'] == 'driver_reference' else None)
            actors.append(sensor)
            sensors.append(sensor)
            encoders[camera['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra',
                '-s', f"{camera['width']}x{camera['height']}", '-r', '20', '-i', '-',
                '-frames:v', '600', '-c:v', 'ffv1', '-level', '1', str(output / (camera['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            sensor.listen(lambda image, name=camera['name']: images.put((name, image)))
        with PipelineCapture(client, vehicle, output, config['case_id'], required_observations=config['required_atoms']) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'alley-capture.jsonl').open('x', buffering=1) as trace:
            for index in range(600):
                vehicle.apply_control(carla.VehicleControl(throttle=0, brake=1, steer=0))
                native_frame = world.tick()
                pose, velocity = vehicle.get_transform(), vehicle.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    encoders[name].stdin.write(image.raw_data)
                    seen.add(name)
                capture.capture(native_frame, index / 20, extra={'video_frame': index})
                frame_map.append(native_frame, index / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({'source_kind': 'original_native_observation', 'video_frame': index,
                                        'native_frame': native_frame, 'time_s': ledger['capture_start_s'] + index / 20,
                                        'source_cameras': {name: index for name in VIEWS},
                                        'vehicle_id': context['vehicle_id'],
                                        'within_alley': inside_polygon(pose.location.x, pose.location.y, context['alley_polygon_xy_m']),
                                        'position_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
                                        'velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
                                        'observed_speed_mps': speed,
                                        'requested_parked_seconds_in_rolling_hour': config['requested_parked_seconds_in_rolling_hour']}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            codes[name] = process.wait(timeout=180)
            require(codes[name] == 0 and (output / (name + '.mkv')).is_file(),
                    'Source camera encode failed: ' + name + ' ' + error.decode()[-200:])
        finished = True
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restored = restore(client, original)
        if finished and len(codes) == 4:
            seal_capture(output, frames=600, restoration=restored, errors=[], encoder_exit_codes=codes,
                         context={'case_id': config['case_id'], 'original_hour_ledger_source': sha(ledger_path)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--alley-context')
    parser.add_argument('--alley-ledger')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((ROOT / 'config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir, 'output directory required')
        execute(config, args.output_dir, args.alley_context or os.environ.get('SCENARIO_ALLEY_CONTEXT'),
                args.alley_ledger or os.environ.get('SCENARIO_ALLEY_LEDGER'), args.host, args.port)
