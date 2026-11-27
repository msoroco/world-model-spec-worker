"""CPU-checked Native caravan route draft; no local recording has been accepted.

The runnable path retains original body and velocity rows with four camera
streams and a canonical frame map. Selected saved processing is pending.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from engineering import CANDIDATES, DURATION_S, FRAMES, GAP_TARGETS_M, RATE_HZ, check as engineering_check, commanded_centers
from geometry import CARAVAN_LANE_ID, CARAVAN_Y_M, ENTRANT_LANE_ID, ENTRANT_Y_M, ROAD_ID, check as geometry_check, open_drive

HERE = Path(__file__).resolve().parent


def cameras():
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': 100,
         'xyz_m': [0, 0, 55], 'pitch_deg': -90, 'yaw_deg': 0},
        {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 95,
         'xyz_m': [2, 0, 3], 'pitch_deg': -5, 'yaw_deg': 0},
        {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fov_deg': 95,
         'xyz_m': [-2, 0, 6], 'pitch_deg': -12, 'yaw_deg': 180},
        {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 90,
         'xyz_m': [0.5, 0.2, 1.7], 'pitch_deg': 0, 'yaw_deg': 0},
    ]


def check(config):
    suffix = config.get('case_suffix')
    candidate = config.get('candidate_id')
    expected = 'training__C228508__NRS-484B-127-3__motor_vehicle_driver__' + str(suffix)
    if config.get('case_id') != expected or config.get('selected_case_id') != expected:
        raise ValueError('Exact caravan case identity differs')
    if config.get('law_id') != 'NRS-484B-127-3' or config.get('cell_id') != 'C228508' or config.get('actor') != 'motor_vehicle_driver':
        raise ValueError('Frozen law/cell/actor differs')
    if config.get('duration_s') != DURATION_S or config.get('rate_hz') != RATE_HZ:
        raise ValueError('Thirty-second 20 Hz source contract differs')
    if suffix not in GAP_TARGETS_M or candidate not in CANDIDATES:
        raise ValueError('Unknown caravan candidate')
    if [(c.get('name'), c.get('width'), c.get('height'), c.get('fov_deg')) for c in config.get('cameras', [])] != [
            (c['name'], c['width'], c['height'], c['fov_deg']) for c in cameras()]:
        raise ValueError('Four source camera profile differs')
    return {'geometry': geometry_check(), 'engineering': engineering_check(suffix, candidate),
            'native_imported': False, 'camera_capture_implemented': True,
            'physical_success_claimed': False}


def body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
    if len(points) != 4:
        raise RuntimeError('Original actor lacks four ground footprint corners')
    return [list(p) for p in points]


def sample(actor, mapping):
    pose = actor.get_transform()
    waypoint = mapping.get_waypoint(pose.location, project_to_road=False)
    if waypoint is None or waypoint.road_id != ROAD_ID:
        raise RuntimeError('Original actor road identity differs')
    velocity = actor.get_velocity()
    return {'native_road_id': waypoint.road_id, 'native_lane_id': waypoint.lane_id,
            'native_body_xy_m': body(actor),
            'native_center_xy_m': [pose.location.x, pose.location.y],
            'native_velocity_xy_mps': [velocity.x, velocity.y],
            'speed_mps': math.hypot(velocity.x, velocity.y)}


def combined_body(first, second):
    points = first['native_body_xy_m'] + second['native_body_xy_m']
    low_x, high_x = min(p[0] for p in points), max(p[0] for p in points)
    low_y, high_y = min(p[1] for p in points), max(p[1] for p in points)
    return [[low_x, low_y], [low_x, high_y], [high_x, high_y], [high_x, low_y]]


def write_new(path, obj):
    with Path(path).open('x') as stream:
        json.dump(obj, stream, indent=2, allow_nan=False)
        stream.write('\n')


def write_joined_camera_frame(frame, spec, source_queue, encoder, numpy_module):
    image = source_queue.get(timeout=30)
    while image.frame < frame:
        image = source_queue.get(timeout=30)
    if image.frame != frame:
        raise RuntimeError('Original camera/Native frame join failed')
    rgba = numpy_module.frombuffer(image.raw_data, dtype=numpy_module.uint8)
    expected = spec['width'] * spec['height'] * 4
    if rgba.size != expected:
        raise ValueError('Original camera source byte count differs')
    rgb = rgba.reshape(spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
    encoder.stdin.write(rgb.tobytes())
    return {'native_frame': frame, 'camera_frame': image.frame,
            'view': spec['name'], 'source_bytes': expected,
            'encoded_input_bytes': spec['width'] * spec['height'] * 3}


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use a new materialized exact-case output directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    saved = snapshot(client)
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for a in prior.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous world ownership required')
    owned = []
    camera_queues = {}
    encoders = {}
    encoder_logs = {}
    capture = None
    changed = False
    error = None
    restored = None
    frames = 0
    try:
        world = client.generate_opendrive_world(open_drive())
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        native_map_sha = hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()
        library = world.get_blueprint_library()
        initial = commanded_centers(config['case_suffix'], config['candidate_id'], 0)
        blueprints = {'lead': 'vehicle.lincoln.mkz_2020',
                      'ego_combination': 'vehicle.lincoln.mkz_2020',
                      'trailer_proxy': 'vehicle.lincoln.mkz_2020',
                      'rear': 'vehicle.lincoln.mkz_2020',
                      'potential_entrant': 'vehicle.lincoln.mkz_2020'}
        actors = {}
        for name in ('lead', 'ego_combination', 'trailer_proxy', 'rear', 'potential_entrant'):
            center = (initial['ego_combination'] - 2.25 if name == 'trailer_proxy'
                      else initial['ego_combination'] + 2.25 if name == 'ego_combination'
                      else initial[name])
            lane_y = ENTRANT_Y_M if name == 'potential_entrant' else CARAVAN_Y_M
            actor = world.spawn_actor(library.find(blueprints[name]),
                                      carla.Transform(carla.Location(x=center, y=lane_y, z=1)))
            owned.append(actor)
            actors[name] = actor
        write_new(output / 'authored-context.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'native_map_sha256': native_map_sha,
            'public_highway_status_verified': False,
            'outside_business_district_verified': False,
            'caravan_membership_verified': False,
            'trailer_coupling_verified': False,
            'potential_entrant_safety_verified': False,
            'camera_capture_implemented': True,
            'initial_native_bodies': {name: body(actor) for name, actor in actors.items()}})
        write_new(output / 'caravan_context.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'public_highway_status_verified': False,
            'outside_business_district_verified': False,
            'caravan_membership_verified': False,
            'trailer_coupling_verified': False,
            'entry_without_danger_judgment': 'unresolved',
            'selected_controller': 'same-speed caravan with source-observed entrant lateral request; no legal cutoff'})
        for spec in cameras():
            blueprint = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', spec['fov_deg']), ('sensor_tick', 0)):
                blueprint.set_attribute(key, str(value))
            xyz = spec['xyz_m']
            camera = world.spawn_actor(blueprint,
                carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                                carla.Rotation(pitch=spec['pitch_deg'], yaw=spec['yaw_deg'])),
                attach_to=actors['ego_combination'])
            owned.append(camera)
            camera_queues[spec['name']] = queue.Queue()
            camera.listen(camera_queues[spec['name']].put)
            encoder_logs[spec['name']] = (output / (spec['name'] + '.encoder.log')).open('x')
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ), '-i', 'pipe:0',
                '-an', '-c:v', 'ffv1', '-level', '1', str(output / (spec['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=encoder_logs[spec['name']])
        capture = PipelineCapture(client, actors['ego_combination'], output, config['case_id'],
                                  required_observations=config.get('required_atoms', []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native_samples.jsonl').open('x') as stream, \
             (output / 'caravan_history.jsonl').open('x') as history, \
             FrameMap(output / 'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                speed = CANDIDATES[config['candidate_id']]
                for name, actor in actors.items():
                    if name == 'potential_entrant':
                        continue
                    actor.set_target_velocity(carla.Vector3D(x=speed, y=0, z=0))
                entrant_y = actors['potential_entrant'].get_transform().location.y
                lateral = 0.875 if index >= 40 and entrant_y < CARAVAN_Y_M - .05 else 0.0
                actors['potential_entrant'].set_target_velocity(carla.Vector3D(x=speed, y=lateral, z=0))
                frame = world.tick()
                observations = {name: sample(actor, mapping) for name, actor in actors.items()}
                if any(observations[name]['native_lane_id'] != CARAVAN_LANE_ID for name in ('lead', 'ego_combination', 'trailer_proxy', 'rear')):
                    raise RuntimeError('Original caravan actor left selected lane')
                if observations['potential_entrant']['native_lane_id'] not in (ENTRANT_LANE_ID, CARAVAN_LANE_ID):
                    raise RuntimeError('Original potential entrant left two-lane corridor')
                row = {'native_frame': frame,
                       'time_s': world.get_snapshot().timestamp.elapsed_seconds - start,
                       'actors': observations,
                       'requested_group_speed_mps': speed,
                       'requested_entrant_lateral_mps': lateral}
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                history.write(json.dumps({'frame': frame, 'time_s': row['time_s'],
                    'participants': {
                        'subject': {'body_vertices_m': observations['lead']['native_body_xy_m'],
                                    'lane_id': observations['lead']['native_lane_id']},
                        'rear': {'body_vertices_m': combined_body(observations['ego_combination'], observations['trailer_proxy']),
                                 'lane_id': observations['ego_combination']['native_lane_id']},
                        'entrant': {'body_vertices_m': observations['potential_entrant']['native_body_xy_m'],
                                    'lane_id': observations['potential_entrant']['native_lane_id']}}},
                    allow_nan=False) + '\n')
                capture.capture(frame, row['time_s'], extra={'c228508_native': row})
                for spec in cameras():
                    write_joined_camera_frame(frame, spec, camera_queues[spec['name']],
                                              encoders[spec['name']], np)
                frame_map.append(frame, row['time_s'])
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless camera encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'owned_actor_cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        if (output / 'authored-context.json').is_file() and (output / 'native_samples.jsonl').is_file():
            write_new(output / 'native-source-inventory.json', {
                'format': 'c228508-original-native-draft-sources-v1',
                'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
                'sha256': {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                           for name in ('authored-context.json', 'native_samples.jsonl')}})
        write_new(output / 'native-draft-report.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'observed_frames': frames, 'expected_frames': FRAMES,
            'world_restoration': restored, 'error': error,
            'selected_delivery': False, 'physical_success_claimed': False})
    if error:
        raise RuntimeError('Native draft failed; inspect native-draft-report.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads((HERE / 'config.json').read_text())
    if args.check:
        print(json.dumps(check(config), allow_nan=False))
    else:
        if not args.output_dir or not args.host or not args.port:
            raise ValueError('Explicit materialized output and owned Native endpoint required')
        execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
