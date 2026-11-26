"""Unselected Native proposal for the two walking-side comparison conditions.

An operator must supply a reviewed road-source packet; CPU checks never contact CARLA.
"""

import argparse
import json
import queue
import math
import subprocess
import os
import hashlib
import traceback
from pathlib import Path

from walking_side import FRAMES, HZ, _source, measure

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
PHYSICAL_CRITERION = {
    'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
    'position_key': 'position_m', 'direction_xy': [-1, 0],
    'minimum_progress_m': 6.0,
    'context_sources': ['reviewed-road-source.json'],
}


def check(config):
    if config.get('law_id') != 'NRS-484B-297-2' or config.get('cell_id') != 'C230259' or config.get('actor') != 'pedestrian':
        raise ValueError('Exact law, cell and actor required')
    if config.get('case_id') not in config.get('selected_case_ids', []) or config.get('condition') not in ('a', 'b'):
        raise ValueError('Exact comparison case required')
    if config.get('duration_s') != 30 or config.get('rate_hz') != HZ or config.get('frames') != FRAMES:
        raise ValueError('Full 30-second 600-frame capture required')
    if tuple(x.get('name') for x in config.get('cameras', [])) != VIEWS:
        raise ValueError('Four named source cameras required')
    for camera in config['cameras']:
        if not all(camera.get(k) for k in ('width', 'height', 'fov_deg', 'pose_strategy', 'location_xyz_m', 'rotation_pyr_deg')) or camera.get('fps') != HZ:
            raise ValueError('Source camera geometry incomplete')
    if (config.get('source_packet_required') is not True or
            config.get('requested_speed_mps') != .4 or
            config.get('walker_spawn_height_adjustment_m') not in (0.0, 0.15) or
            config.get('physical_completion') != PHYSICAL_CRITERION or
            config.get('legal_verdict') is not None):
        raise ValueError('Source provenance and unknown outcome required')
    return {'case_id': config['case_id'], 'frames': FRAMES, 'rate_hz': HZ,
            'source_views': VIEWS, 'source_packet_required': True,
            'physical_completion': False, 'legal_verdict': None, 'carla_contacted': False}


def _packet(path, config):
    packet = json.loads(Path(path).read_text())
    traffic = _source(packet)
    if packet.get('source_kind') != 'original_native':
        raise ValueError('Native execution requires a reviewed original map packet')
    if packet.get('map_name') is None or packet.get('pedestrian_spawn_transform') is None or packet.get('vehicle_spawn_transform') is None:
        raise ValueError('Reviewed Native map and participant spawns required')
    if packet.get('condition') != config['condition']:
        raise ValueError('Source packet selected another condition')
    if packet.get('pedestrian_route_side') != ('traffic_left' if config['condition'] == 'a' else 'traffic_right'):
        raise ValueError('Source route side differs from planned comparison')
    direction = packet.get('pedestrian_direction_xyz')
    if not isinstance(direction, list) or len(direction) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in direction):
        raise ValueError('Pedestrian direction missing')
    dot = direction[0] * traffic[0] + direction[1] * traffic[1]
    if dot >= 0:
        raise ValueError('Pedestrian must face approaching traffic in both conditions')
    if not 0 < packet.get('pedestrian_speed_mps', 0) <= 3 or not 0 <= packet.get('vehicle_throttle', -1) <= 1:
        raise ValueError('Participant control source invalid')
    return packet


def execute(config, source_path, output_path, host, port):
    """Capture source pixels and positions; actual pixels and physical success remain unconfirmed."""
    check(config)
    packet = _packet(source_path, config)
    import carla
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import FrameMap, physical_result, write_result, seal_capture
    from worker_exchange.media import compose_four_views
    from pipeline_capture import PipelineCapture
    from walker_capture_adapter import adapt
    from source_channels import write_channels, rows as read_source_rows
    import numpy as np

    def transform(data, height_adjustment=0.0):
        location = dict(data['location'])
        location['z'] += height_adjustment
        return carla.Transform(carla.Location(**location), carla.Rotation(**data['rotation']))

    output = Path(output_path)
    if not output.is_dir() or not (output / 'config.json').is_file() or not (output / 'construction.json').is_file():
        raise ValueError('Fresh materialized Native attempt with config and construction required')
    retained_packet = output / 'reviewed-road-source.json'
    if retained_packet.exists():
        if hashlib.sha256(retained_packet.read_bytes()).digest() != hashlib.sha256(Path(source_path).read_bytes()).digest():
            raise ValueError('Original reviewed road packet differs from retained attempt source')
    else:
        retained_packet.write_bytes(Path(source_path).read_bytes())
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    initial = snapshot(client)
    if initial['settings'].synchronous_mode:
        raise ValueError('Exclusive idle asynchronous Native world required')
    actors = []
    cameras = []
    received = queue.Queue()
    capture = None
    encoders = {}
    encoder_logs = {}
    encoder_exit_codes = {}
    error = None
    restored = None
    result = None
    try:
        if world.get_map().name != packet['map_name']:
            raise ValueError('Native map differs from reviewed source packet')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / HZ
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        pedestrian = world.try_spawn_actor(blueprints.find(packet['pedestrian_blueprint']),
                                           transform(packet['pedestrian_spawn_transform'],
                                                     config['walker_spawn_height_adjustment_m']))
        vehicle = world.try_spawn_actor(blueprints.find(packet['vehicle_blueprint']), transform(packet['vehicle_spawn_transform']))
        if pedestrian is None or vehicle is None:
            raise ValueError('Participant spawn occupied')
        actors += [pedestrian, vehicle]
        for camera in config['cameras']:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(camera['width']))
            bp.set_attribute('image_size_y', str(camera['height']))
            bp.set_attribute('fov', str(camera['fov_deg']))
            loc = camera['location_xyz_m']
            rot = camera['rotation_pyr_deg']
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=loc[0], y=loc[1], z=loc[2]),
                                                            carla.Rotation(pitch=rot[0], yaw=rot[1], roll=rot[2])), attach_to=vehicle)
            actors.append(sensor)
            cameras.append(sensor)
            sensor.listen(lambda image, name=camera['name']: received.put((name, image)))
            encoder_logs[camera['name']] = (output / (camera['name'] + '.encoder.log')).open('x')
            encoders[camera['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f"{camera['width']}x{camera['height']}", '-r', str(HZ),
                '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output / (camera['name'] + '.mkv'))], stdin=subprocess.PIPE,
                stderr=encoder_logs[camera['name']])
        direction = packet['pedestrian_direction_xyz']
        control = carla.WalkerControl(direction=carla.Vector3D(x=direction[0], y=direction[1], z=direction[2]),
                                      speed=packet['pedestrian_speed_mps'])
        (output / 'channels').mkdir()
        capture_client, capture_ego = adapt(client, pedestrian)
        capture = PipelineCapture(capture_client, capture_ego, output, config['case_id'], required_observations=config.get('required_atoms', []))
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
             (output / 'walking-source.jsonl').open('x', buffering=1) as walk_source, \
             (output / 'channels' / 'kin.position.jsonl').open('x', buffering=1) as position, \
             (output / 'channels' / 'kin.speed.jsonl').open('x', buffering=1) as speed:
            for index in range(FRAMES):
                pedestrian.apply_control(control)
                vehicle.set_autopilot(False)
                vehicle.apply_control(carla.VehicleControl(throttle=packet['vehicle_throttle'], brake=0, steer=0))
                tick = world.tick()
                seen = set()
                pixel_hashes = {}
                while len(seen) != len(VIEWS):
                    name, image = received.get(timeout=15)
                    if image.frame < tick:
                        continue
                    if image.frame != tick or name in seen:
                        raise ValueError('Original source camera/frame join failed')
                    camera = next(item for item in config['cameras'] if item['name'] == name)
                    pixels = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(camera['height'], camera['width'], 4)[:, :, :3][:, :, ::-1].tobytes()
                    pixel_hashes[name] = hashlib.sha256(pixels).hexdigest()
                    encoders[name].stdin.write(pixels)
                    seen.add(name)
                p = pedestrian.get_transform()
                p_velocity = pedestrian.get_velocity()
                v = vehicle.get_transform()
                time_s = index / HZ
                applied = pedestrian.get_control()
                capture.capture(tick, time_s, extra={'video_frame': index, 'pedestrian_id': pedestrian.id,
                                                     'vehicle_id': vehicle.id,
                                                     'walker_control': {'direction_xyz': [applied.direction.x, applied.direction.y, applied.direction.z],
                                                                        'speed_mps': applied.speed, 'jump': applied.jump,
                                                                        'vehicle_fields_applicable': False}})
                frame_map.append(tick, time_s, native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds,
                                 source_rgb_sha256=pixel_hashes)
                pose = [p.location.x, p.location.y, p.location.z]
                velocity = [p_velocity.x, p_velocity.y, p_velocity.z]
                walk_source.write(json.dumps({'source_kind': 'original_native', 'video_frame': index, 'native_frame': tick,
                                              'time_s': time_s, 'pedestrian_id': pedestrian.id, 'vehicle_id': vehicle.id,
                                              'pedestrian_xy_m': pose[:2],
                                              'vehicle_xy_m': [v.location.x, v.location.y],
                                              'pedestrian_heading_xy': velocity[:2]}) + '\n')
                position.write(json.dumps({'time_s': time_s, 'value': pose}) + '\n')
                speed.write(json.dumps({'time_s': time_s, 'value': math.sqrt(sum(value * value for value in velocity))}) + '\n')
        source_rows = [json.loads(line) for line in (output / 'walking-source.jsonl').read_text().splitlines()]
        observed = measure(packet, source_rows)
        wanted_side = 'traffic_left' if config['condition'] == 'a' else 'traffic_right'
        side_frames = observed['counts'][wanted_side]
        face_frames = observed['counts']['facing_opposite_traffic']
        target = {'target': 'continuous_requested_side_and_opposing_heading',
                  'requested': {'side': wanted_side, 'frames': FRAMES},
                  'measured': {'side_frames': side_frames, 'opposing_heading_frames': face_frames},
                  'method': 'source-bound original Native pedestrian and vehicle trace',
                  'tolerance': 0, 'matched': side_frames == face_frames == FRAMES,
                  'physical_cause_confirmed': False,
                  'cause_evidence': 'walking-source.jsonl and reviewed-road-source.json; independent pixel review pending'}
        result = {'case_id': config['case_id'], 'measured_values': observed['counts'],
                  'target_checks': [target], 'setup_confirmed': False,
                  'behavior_attempted': False, 'maneuver_completed': False,
                  'termination_reason': 'Full source window captured; saved review pending',
                  'physical_failure_flags': {'source_camera_visibility_unverified': True},
                  'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'],
                  'video_frame_map_reference': 'video_frames.jsonl',
                  'recording_description': config['recording_description'],
                  'recording_evidence': [{'name': item['name'], 'unit': item['unit'],
                                          'reference': 'channels/' + item['name'] + '.jsonl'}
                                         for item in config['recording_description']['channels']] +
                                        [{'name': 'highway_boundary_source', 'unit': 'structured',
                                          'reference': 'reviewed-road-source.json'}],
                  'realized_observables': {}}
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
                encoder_exit_codes[name] = encoder.wait(timeout=180)
                if encoder_exit_codes[name]:
                    raise ValueError('Four-view source encoding failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for sensor in cameras:
            try:
                sensor.stop()
            except BaseException as exc:
                error = error or {'sensor_stop_error': str(exc)}
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_destroy_error': str(exc)}
        try:
            restored = restore(client, initial)
        except BaseException as exc:
            error = error or {'world_restore_error': str(exc)}
    if error:
        (output / 'native-run-status.json').write_text(json.dumps({'errors': [error]}, indent=2) + '\n')
        raise ValueError('Original Native capture failed: ' + str(error.get('message', error)))
    composition = compose_four_views({name: output / (name + '.mkv') for name in VIEWS},
                                     output / 'video_frames.jsonl', output / 'raw.mkv')
    (output / 'four-view-receipt.json').write_text(json.dumps(composition, indent=2) + '\n')
    write_channels(output, packet, read_source_rows(output / 'walking-source.jsonl'),
                   read_source_rows(output / 'trace.jsonl'))
    seal_capture(output, frames=FRAMES, restoration=restored, errors=[], encoder_exit_codes=encoder_exit_codes,
                 context={'law_id': config['law_id'], 'cell_id': config['cell_id'],
                          'source_packet': 'reviewed-road-source.json', 'legal_verdict': None})
    write_result(output, physical_result(output, result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--source')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.output_dir:
            raise ValueError('Attempt output dir required')
        source = args.source or os.environ.get('REVIEWED_ROAD_PACKET') or str(Path(args.output_dir) / 'reviewed-road-source.json')
        if not Path(source).is_file():
            raise ValueError('Missing required source: reviewed-road-source.json')
        execute(config, source, args.output_dir, args.host, args.port)
