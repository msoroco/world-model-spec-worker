"""Source-gated Native diagonal capture; CPU --check does not import CARLA."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import traceback

from native_request import (FRAMES, RATE_HZ, START, FINISH, camera_plan,
                            apply_walker_control, apply_device_and_readback,
                            verify_authority_sources)

HERE = Path(__file__).resolve().parent
HEAD = 'c109166-diagonal-crossing-head'


def check(config):
    if (config.get('cell_id'), config.get('law_id'), config.get('actor')) != ('C109166', 'NRS-484B-287-1e', 'pedestrian'):
        raise ValueError('frozen diagonal assignment identity differs')
    if config.get('case_suffix') not in ('controlled_1', 'controlled_2'):
        raise ValueError('exact controlled diagonal case required')
    if config.get('case_id') != 'training__C109166__NRS-484B-287-1e__pedestrian__' + config['case_suffix']:
        raise ValueError('exact case identity differs')
    if (config.get('rate_hz'), config.get('duration_s')) != (RATE_HZ, 30):
        raise ValueError('30-second 20 Hz capture required')
    if [(c['name'], c['width'], c['height']) for c in config.get('cameras', [])] != [
            (c['name'], c['width'], c['height']) for c in camera_plan()]:
        raise ValueError('four source-camera dimensions differ')
    if not isinstance(config.get('opendrive_signal_id'), str) or not config['opendrive_signal_id']:
        raise ValueError('surveyed OpenDRIVE head identity required')
    if config.get('entry_proxy_x_m') != -5.5:
        raise ValueError('authored road-entry proxy differs; physical boundary review required')
    if config.get('driver_reference_height_m') not in (2.2, 3.0):
        raise ValueError('device camera height differs from approved candidates')
    return {'case_id': config['case_id'], 'frames': FRAMES, 'camera_count': 4,
            'native_executed': False, 'official_status_verified': False}


def _write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def _footprint(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(round(vertex.x, 5), round(vertex.y, 5)) for vertex in vertices})
    if len(points) != 4:
        raise ValueError('original walker ground footprint incomplete')
    return [list(point) for point in points]


class NativeHead:
    """Actuate one surveyed CARLA light and separately sample its physical state.

    Green/red do not themselves prove diagonal applicability or official status.
    """
    def __init__(self, actor, carla, opendrive_id):
        self.actor, self.carla, self.opendrive_id = actor, carla, str(opendrive_id)

    def command(self, device_id, state):
        if device_id != HEAD:
            raise ValueError('another diagonal head was requested')
        value = 'Green' if state == 'diagonal_walk' else 'Red' if state == 'diagonal_dont_walk' else None
        if value is None:
            raise ValueError('unsupported diagonal display request')
        self.actor.set_state(getattr(self.carla.TrafficLightState, value))
        self.actor.freeze(True)

    def observe(self, device_id):
        if device_id != HEAD or str(self.actor.get_opendrive_id()) != self.opendrive_id:
            raise ValueError('surveyed head changed')
        actual = str(self.actor.get_state()).split('.')[-1]
        if actual not in ('Green', 'Red'):
            raise ValueError('unsupported Native traffic-light state')
        return {'source_kind': 'native_device_readback', 'device_id': HEAD,
                'displayed_instruction': 'diagonal_walk' if actual == 'Green' else 'diagonal_dont_walk',
                'native_frame': self.frame, 'source_ref': f'traffic-light-actor:{self.actor.id}',
                'native_actor_id': self.actor.id, 'opendrive_id': self.opendrive_id,
                'native_state': actual}


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('newly materialized exact attempt required')
    source_dir = os.environ.get('SCENARIO_DIAGONAL_AUTHORITY_DIR')
    if not source_dir:
        raise ValueError('SCENARIO_DIAGONAL_AUTHORITY_DIR required before Native mutation')
    source_dir = Path(source_dir).resolve()
    receipt_path = source_dir / 'authority-receipt.json'
    if not receipt_path.is_file():
        raise ValueError('original authority receipt required before Native mutation')
    original_receipt = json.loads(receipt_path.read_text())
    verify_authority_sources(source_dir, original_receipt)
    for source in original_receipt.values():
        relative = Path(source['path'])
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError('attempt already contains authority source: ' + str(relative))
        shutil.copy2(source_dir / relative, destination)
    if (output / 'authority-receipt.json').exists():
        raise ValueError('attempt already contains authority receipt')
    shutil.copy2(receipt_path, output / 'authority-receipt.json')
    authority = verify_authority_sources(output, original_receipt)
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    world = client.get_world()
    state = snapshot(client)
    if state['settings'].synchronous_mode or any(actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
                                                  for actor in world.get_actors()):
        raise ValueError('exclusive idle asynchronous Native world required')
    heads = [actor for actor in world.get_actors() if actor.type_id.startswith('traffic.traffic_light')
             and str(actor.get_opendrive_id()) == config['opendrive_signal_id']]
    if len(heads) != 1:
        raise ValueError('exactly one surveyed Native head required')
    head = NativeHead(heads[0], carla, config['opendrive_signal_id'])
    owned, encoders, logs, queues = [], {}, {}, {}
    capture = None
    changed = False
    error = None
    restored = None
    frames = 0
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        changed = True
        blueprints = sorted(world.get_blueprint_library().filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        if not blueprints:
            raise ValueError('Native walker blueprint absent')
        walker = world.try_spawn_actor(blueprints[0], carla.Transform(
            carla.Location(x=START[0], y=START[1], z=.5), carla.Rotation(yaw=45)))
        if walker is None:
            raise ValueError('Native diagonal walker spawn failed')
        owned.append(walker)
        for spec in camera_plan():
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            location = list(spec['location_xyz_m'])
            if spec['name'] == 'driver_reference':
                location[2] = config['driver_reference_height_m']
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(*location), carla.Rotation(*spec['rotation_pitch_yaw_roll_deg'])))
            if sensor is None:
                raise ValueError('Native camera spawn failed: ' + spec['name'])
            owned.append(sensor)
            queues[spec['name']] = queue.Queue()
            sensor.listen(queues[spec['name']].put)
            logs[spec['name']] = (output / (spec['name'] + '.encoder.log')).open('x')
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f"{spec['width']}x{spec['height']}",
                '-r', str(RATE_HZ), '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output / (spec['name'] + '.mkv'))], stdin=subprocess.PIPE, stderr=logs[spec['name']])
        capture = PipelineCapture(client, walker, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        start_time = world.get_snapshot().timestamp.elapsed_seconds
        previous_x = None
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'pedestrian-original.jsonl').open('x') as people, \
                (output / 'device-original.jsonl').open('x') as devices, \
                (output / 'camera-sources.jsonl').open('x') as cameras:
            for index in range(FRAMES):
                apply_walker_control(walker, carla, config['case_suffix'], index)
                head.command(HEAD, 'diagonal_dont_walk' if config['case_suffix'] == 'controlled_2' and 100 <= index < 160 else 'diagonal_walk')
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start_time
                head.frame = frame
                observation = apply_device_and_readback(head, config['case_suffix'], index, native_frame=frame)
                observation['native_frame'] = frame
                observation['time_s'] = time_s
                pose = walker.get_transform().location
                body = _footprint(walker)
                crossed_proxy = previous_x is not None and previous_x < config['entry_proxy_x_m'] <= pose.x
                previous_x = pose.x
                person = {'native_frame': frame, 'time_s': time_s, 'walker_id': walker.id,
                          'center_xy_m': [pose.x, pose.y], 'footprint_xy_m': body,
                          'road_entry_proxy_observed': crossed_proxy,
                          'road_boundary_review_pending': True}
                capture.capture(frame, time_s, extra={'diagonal_observation': {'person': person, 'device': observation}})
                pixel_hashes = {}
                for spec in camera_plan():
                    image = queues[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = queues[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise ValueError('Native camera/frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    raw = rgb.tobytes()
                    digest = hashlib.sha256(raw).hexdigest()
                    pixel_hashes[spec['name']] = digest
                    encoders[spec['name']].stdin.write(raw)
                    cameras.write(json.dumps({'camera': spec['name'], 'frame': index,
                        'native_frame': frame, 'time_s': time_s, 'width': spec['width'],
                        'height': spec['height'], 'source_path': spec['name'] + '.mkv',
                        'source_sha256': digest}) + '\n')
                person['source_rgb_sha256'] = pixel_hashes
                people.write(json.dumps(person) + '\n')
                devices.write(json.dumps(observation) + '\n')
                frame_map.append(frame, time_s, source_rgb_sha256=pixel_hashes)
                frames += 1
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
                    raise ValueError('lossless camera encoder failed: ' + name)
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
        _write(output / 'native-capture-report.json', {'case_id': config['case_id'],
            'frames': frames, 'expected_frames': FRAMES, 'error': error, 'restoration': restored,
            'official_status_verified': False, 'actual_pixels_reviewed': False,
            'physical_completion_verified': False})
    if error:
        raise RuntimeError('Native diagonal capture failed; inspect native-capture-report.json')


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
            raise ValueError('explicit Native endpoint and attempt required')
        execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
