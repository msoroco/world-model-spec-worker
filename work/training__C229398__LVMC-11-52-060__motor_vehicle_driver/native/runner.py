"""C229398 30-second Native capture proposal; --check needs no CARLA server.

An attached prop and trailer must be verified in the original Native capture.
Map lane edges are only proposed curb locations until source review.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from projection_measure import FEET_PER_METER
from source_footprints import vertices

FRAMES = 600
RATE_HZ = 20
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ASSIGNMENT = 'training__C229398__LVMC-11-52-060__motor_vehicle_driver'
TARGETS = {'below_15_ft': 14, 'at_15_ft': 15, 'above_15_ft': 16}
CANDIDATES = {
    'primary': (2.4, -5, 12),
    'fallback1': (1.8, -5, 12),
    'fallback2': (2.4, -7, 12),
    'fallback3': (2.4, -5, 16),
}


def check(config):
    suffix = config.get('case_suffix')
    if (suffix not in TARGETS or config.get('case_id') != ASSIGNMENT + '__' + suffix
            or config.get('selected_case_id') != config.get('case_id')
            or config.get('cell_id') != 'C229398'
            or config.get('law_id') != 'LVMC-11-52-060'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('target_projection_ft') != TARGETS[suffix]
            or config.get('duration_s') != 30 or config.get('rate_hz') != RATE_HZ
            or config.get('candidate_id') not in CANDIDATES):
        raise ValueError('Exact C229398 case or full capture contract differs')
    actual = (config.get('load_height_m'), config.get('trailer_rear_m'),
              config.get('camera_distance_m'))
    if actual != CANDIDATES[config['candidate_id']]:
        raise ValueError('Candidate physical knobs differ')
    cameras = config.get('cameras')
    if (not isinstance(cameras, list) or [x.get('name') for x in cameras] != list(VIEWS)
            or [(x.get('width'), x.get('height')) for x in cameras]
            != [(1280, 720)] * 4):
        raise ValueError('Four source cameras required')
    if (config.get('vehicle_blueprint') != 'vehicle.tesla.model3'
            or config.get('load_filter') != 'static.prop.*'
            or config.get('trailer_filter') != 'vehicle.*'):
        raise ValueError('Native participant or camera configuration differs')
    return {'case_id': config['case_id'], 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'camera_views': list(VIEWS),
            'target_projection_ft': TARGETS[suffix],
            'candidate_id': config['candidate_id'],
            'source_kind': 'native', 'carla_imported': False,
            'curb_reviewed': False, 'physical_acceptance_claimed': False}


def actor_row(actor, role, vehicle_id=None):
    transform = actor.get_transform()
    box = actor.bounding_box
    center = transform.transform(box.location)
    row = {'actor_id': str(actor.id), 'role': role,
           'center_xy_m': [center.x, center.y],
           'half_extent_xy_m': [box.extent.x, box.extent.y],
           'yaw_deg': transform.rotation.yaw + box.rotation.yaw,
           'blueprint': actor.type_id}
    if vehicle_id is not None:
        row['attached_to'] = str(vehicle_id)
    return row


def projection_ft(actors, origin, normal):
    return max((point[0] - origin[0]) * normal[0] +
               (point[1] - origin[1]) * normal[1]
               for actor in actors.values() for point in vertices(actor)) * FEET_PER_METER


def _write_new(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use a fresh materialized exact candidate directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    saved = snapshot(client)
    if saved['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in prior.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, queues, encoders, logs = [], {}, {}, {}
    capture, changed, restored, error, count = None, False, None, None, 0
    try:
        world = prior
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        changed = True
        world.set_weather(carla.WeatherParameters.ClearNoon)
        library = world.get_blueprint_library()
        spawn = sorted(world.get_map().get_spawn_points(),
                       key=lambda p: (round(p.location.x, 3), round(p.location.y, 3)))
        if not spawn:
            raise RuntimeError('No Native road spawn point')
        ego = None
        for location in spawn:
            ego = world.try_spawn_actor(library.find(config['vehicle_blueprint']), location)
            if ego is not None:
                break
        if ego is None:
            raise RuntimeError('Native vehicle spawn failed')
        owned.append(ego)
        ego.set_simulate_physics(False)
        props = sorted(library.filter(config['load_filter']), key=lambda x: x.id)
        trailers = sorted(library.filter(config['trailer_filter']), key=lambda x: x.id)
        trailers = [bp for bp in trailers if bp.id != config['vehicle_blueprint']]
        if not props or not trailers:
            raise RuntimeError('Native load or trailer blueprint unavailable')
        load = world.try_spawn_actor(props[0], carla.Transform(
            carla.Location(x=0, y=0, z=config['load_height_m'])), ego,
            carla.AttachmentType.Rigid)
        trailer = world.try_spawn_actor(trailers[0], carla.Transform(
            carla.Location(x=config['trailer_rear_m'], y=0, z=0)), ego,
            carla.AttachmentType.Rigid)
        if load is None or trailer is None:
            raise RuntimeError('Native rigid load/trailer attachment failed')
        owned.extend((load, trailer))
        for actor in (load, trailer):
            if actor.type_id.startswith('vehicle.'):
                actor.set_simulate_physics(False)
        waypoint = world.get_map().get_waypoint(ego.get_location(), project_to_road=False)
        if waypoint is None or waypoint.lane_width <= 0:
            raise RuntimeError('Native lane-edge proposal unavailable')
        heading = math.radians(waypoint.transform.rotation.yaw)
        right = [-math.sin(heading), math.cos(heading)]
        origin = [waypoint.transform.location.x + right[0] * waypoint.lane_width / 2,
                  waypoint.transform.location.y + right[1] * waypoint.lane_width / 2]
        normal = [-right[0], -right[1]]
        world.tick()
        initial = {'vehicle': actor_row(ego, 'vehicle'),
                   'load': actor_row(load, 'load', ego.id),
                   'trailer': actor_row(trailer, 'trailer', ego.id)}
        shift_m = ((config['target_projection_ft'] -
                    projection_ft(initial, origin, normal)) / FEET_PER_METER)
        moved = ego.get_transform()
        moved.location.x += normal[0] * shift_m
        moved.location.y += normal[1] * shift_m
        ego.set_transform(moved)
        world.tick()
        _write_new(output / 'native-curb-proposal.json', {
            'format': 'c229398-curb-proposal-v1', 'source_kind': 'native_map_readback',
            'origin_xy_m': origin, 'street_normal_xy': normal,
            'lane_width_m': waypoint.lane_width, 'road_id': waypoint.road_id,
            'lane_id': waypoint.lane_id,
            'native_map_sha256': hashlib.sha256(
                world.get_map().to_opendrive().encode()).hexdigest(),
            'reviewed': False, 'curb_identity_verified': False})
        for camera in config['cameras']:
            name, width, height = camera['name'], camera['width'], camera['height']
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            offsets = {'overview': (-config['camera_distance_m'], 0, 9),
                       'approach': (-6, 5, 4),
                       'reference_corner': (-2, 7, 3),
                       'driver_reference': (1, 4, 3)}
            x, y, z = offsets[name]
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=-20)), attach_to=ego)
            owned.append(sensor)
            queues[name] = queue.Queue()
            sensor.listen(queues[name].put)
            logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', str(RATE_HZ), '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=logs[name])
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False, required_observations=[])
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native-raw-actors.jsonl').open('x') as raw, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(FRAMES):
                native_frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                actors = {'vehicle': actor_row(ego, 'vehicle'),
                          'load': actor_row(load, 'load', ego.id),
                          'trailer': actor_row(trailer, 'trailer', ego.id)}
                measured_ft = projection_ft(actors, origin, normal)
                if abs(measured_ft - config['target_projection_ft']) > 0.5:
                    raise RuntimeError('Native projection missed requested setting')
                raw.write(json.dumps({'frame': index, 'native_frame': native_frame,
                                      'time_s': time_s, 'source_kind': 'native',
                                      'actors': actors,
                                      'proposed_projection_ft': measured_ft},
                                     allow_nan=False) + '\n')
                capture.capture(native_frame, time_s)
                camera_hashes = {}
                for camera in config['cameras']:
                    name, width, height = camera['name'], camera['width'], camera['height']
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Native camera/frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1].tobytes()
                    encoders[name].stdin.write(rgb)
                    camera_hashes[name] = hashlib.sha256(rgb).hexdigest()
                frame_map.write(json.dumps({'video_frame': index,
                                            'carla_frame': native_frame,
                                            'native_frame': native_frame,
                                            'time_s': time_s,
                                            'camera_rgb_sha256': camera_hashes},
                                           allow_nan=False) + '\n')
                count += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, process in encoders.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'restore_error': str(exc)}
        _write_new(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'requested_frames': FRAMES,
            'observed_frames': count, 'restoration': restored, 'error': error,
            'curb_reviewed': False, 'attachment_verified': False,
            'camera_framing_verified': False, 'accepted': False})
    if error:
        raise RuntimeError('Native capture failed; see native-capture-report.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Native capture requires --output-dir, --host and --port')
        execute(config, args.output_dir, args.host, args.port)
