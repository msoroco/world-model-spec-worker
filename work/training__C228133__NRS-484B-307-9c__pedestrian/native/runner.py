"""C228133 Native capture proposal; --check is CPU only.

An existing Native traffic-light pair is a physical staging proposal. Its red
and green actor states never establish a visible turn arrow or legal governance.
The original pixels and map must pass independent review after capture.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from source_capture import (VIEWS, frame_map_row, pedestrian_device_row,
                            pedestrian_row, signal_state_row)
from signal_display import draw as draw_signal_display, segments as signal_segments
from fallback_trigger import digest as source_digest, evaluate as evaluate_path_trigger

HERE = Path(__file__).resolve().parent
RATE_HZ = 20
FRAMES = 600


def camera_specs(config, anchor, forward, right):
    """Four fixed world cameras watching the approach, boundary and signal."""
    def point(along, across, height):
        return (anchor.x + along * forward.x + across * right.x,
                anchor.y + along * forward.y + across * right.y, height)
    distance = config['camera_distance_m']
    return (
        ('overview', 1920, 1080, point(-distance, 0, 9), -28),
        ('approach', 1280, 720, point(-distance / 2, -4, 4), -18),
        ('reference_corner', 1280, 720, point(0, -5, 4), -30),
        ('driver_reference', 1280, 720, point(3, 4, 3), -12),
    )


def check(config):
    expected_case = ('training__C228133__NRS-484B-307-9c__pedestrian__'
                     + config['case_suffix'])
    if config.get('case_id') != expected_case or \
            config.get('selected_case_id') != expected_case or \
            config.get('case', {}).get('case_id') != expected_case or \
            config.get('cell_id') != 'C228133' or \
            config.get('law_id') != 'NRS-484B-307-9c' or \
            config.get('actor') != 'pedestrian':
        raise ValueError('Exact C228133 assignment identity differs')
    if config['case_suffix'] not in ('reference', 'contrast') or \
            config.get('duration_s') != 30 or config.get('rate_hz') != RATE_HZ:
        raise ValueError('Exact comparison case or full capture duration differs')
    if config.get('pedestrian_enters_highway_requested') != \
            (config['case_suffix'] == 'contrast'):
        raise ValueError('Only planned entry comparison variable may differ')
    if [cam.get('name') for cam in config['cameras']] != list(VIEWS) or \
            [(cam.get('width'), cam.get('height')) for cam in config['cameras']] != \
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)]:
        raise ValueError('Four-camera capability contract differs')
    if config.get('signal_pair_radius_m', 0) <= 0 or \
            config.get('camera_distance_m', 0) <= 0 or \
            config.get('walker_speed_mps', 0) <= 0:
        raise ValueError('Missing finite physical engineering settings')
    if len(signal_segments()) != 35:
        raise ValueError('Visible signal staging geometry differs')
    return {'case_id': expected_case, 'frames': FRAMES, 'camera_views': list(VIEWS),
            'staged_display_segments': len(signal_segments()),
            'native_imported': False, 'turn_arrow_pixels_verified': False,
            'signal_governance_verified': False,
            'other_device_permission_verified': False,
            'physical_acceptance_claimed': False}


def _write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def _choose_pair(world, radius_m):
    lights = sorted((actor for actor in world.get_actors()
                     if actor.type_id.startswith('traffic.traffic_light')),
                    key=lambda actor: actor.id)
    pairs = []
    for index, red in enumerate(lights):
        for green in lights[index + 1:]:
            distance = red.get_location().distance(green.get_location())
            if distance <= radius_m:
                pairs.append((distance, red.id, green.id, red, green))
    if not pairs:
        raise RuntimeError('No two distinct nearby Native traffic-light actors')
    _, _, _, red, green = min(pairs, key=lambda row: row[:3])
    return red, green


def _camera_rgb(image, width, height):
    import numpy as np
    rgba = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(height, width, 4)
    return rgba[:, :, :3][:, :, ::-1].tobytes()


def execute(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use a newly materialized exact candidate directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    state = snapshot(client)
    if state['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in prior.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, queues, encoders, logs = [], {}, {}, {}
    capture = None
    changed = False
    restored = None
    error = None
    count = 0
    original_light_states = []
    try:
        world = prior
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        changed = True
        red, green = _choose_pair(world, config['signal_pair_radius_m'])
        for actor, new_state in ((red, carla.TrafficLightState.Red),
                                 (green, carla.TrafficLightState.Green)):
            original_light_states.append((actor, actor.get_state(), actor.is_frozen()))
            actor.set_state(new_state)
            actor.freeze(True)
        anchor = red.get_location()
        waypoint = world.get_map().get_waypoint(anchor, project_to_road=True)
        if waypoint is None or waypoint.lane_width <= 0:
            raise RuntimeError('Native signal lacks a measurable nearby road lane')
        rotation = waypoint.transform.rotation
        heading = math.radians(rotation.yaw)
        forward = carla.Vector3D(math.cos(heading), math.sin(heading), 0)
        right = carla.Vector3D(-forward.y, forward.x, 0)
        lane_center = waypoint.transform.location
        road_half_width = waypoint.lane_width / 2
        start_offset = road_half_width + config['spawn_clearance_m']
        spawn = carla.Location(x=lane_center.x + start_offset * right.x,
                               y=lane_center.y + start_offset * right.y,
                               z=lane_center.z + 0.5)
        walkers = sorted(world.get_blueprint_library().filter('walker.pedestrian.*'),
                         key=lambda bp: bp.id)
        if not walkers:
            raise RuntimeError('No Native pedestrian blueprint available')
        walker = world.try_spawn_actor(walkers[0], carla.Transform(
            spawn, carla.Rotation(yaw=rotation.yaw - 90)))
        if walker is None:
            raise RuntimeError('Native walker spawn failed')
        owned.append(walker)
        road_side = ('at_or_above_y' if right.y < 0 else 'at_or_below_y')
        if abs(right.y) < 0.95:
            raise RuntimeError('Road-entry y boundary requires aligned Native road')
        boundary_y = lane_center.y + road_half_width * right.y
        display_center = carla.Location(
            x=lane_center.x + (road_half_width + 0.5) * right.x,
            y=lane_center.y + (road_half_width + 0.5) * right.y,
            z=lane_center.z + 3.5)
        _write_new(output / 'road-boundary.json', {
            'format': 'pedestrian-road-boundary-v1',
            'source_kind': 'native_map_readback', 'road_side': road_side,
            'boundary_y_m': boundary_y,
            'native_road_id': waypoint.road_id,
            'native_lane_id': waypoint.lane_id,
            'lane_width_m': waypoint.lane_width,
            'highway_legal_status': 'unreviewed',
            'dedication_and_public_use': 'unreviewed'})
        for name, width, height, xyz, pitch in camera_specs(
                config, lane_center, forward, right):
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            x, y, z = xyz
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z),
                carla.Rotation(yaw=rotation.yaw, pitch=pitch)))
            owned.append(camera)
            queues[name] = queue.Queue()
            camera.listen(queues[name].put)
            logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', str(RATE_HZ), '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=logs[name])
        capture = PipelineCapture(client, walker, output, config['case_id'],
                                  visibility=False,
                                  required_observations=config['required_atoms'])
        start_time = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native-pedestrian-frames.jsonl').open('x') as pedestrians, \
             (output / 'native-signal-frames.jsonl').open('x') as signals, \
             (output / 'native-pedestrian-device-frames.jsonl').open('x') as devices, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(FRAMES):
                draw_signal_display(world, carla, display_center, forward)
                speed = config['walker_speed_mps'] if (
                    config['pedestrian_enters_highway_requested'] and
                    index >= config['entry_start_frame']) else 0.0
                walker.apply_control(carla.WalkerControl(
                    direction=carla.Vector3D(-right.x, -right.y, 0), speed=speed))
                native_frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start_time
                capture.capture(native_frame, time_s)
                rgb = {}
                for name, width, height, _, _ in camera_specs(
                        config, lane_center, forward, right):
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera and Native frame join differs')
                    rgb[name] = _camera_rgb(image, width, height)
                    encoders[name].stdin.write(rgb[name])
                rows = (pedestrian_row(index, native_frame, time_s, walker, road_side),
                        signal_state_row(index, native_frame, time_s, red, green),
                        pedestrian_device_row(index, native_frame, time_s),
                        frame_map_row(index, native_frame, time_s, rgb))
                for stream, row in zip((pedestrians, signals, devices, frame_map), rows):
                    stream.write(json.dumps(row, allow_nan=False) + '\n')
                count += 1
        _write_new(output / 'native-source-context.json', {
            'red_actor_id': red.id, 'green_actor_id': green.id,
            'native_map_sha256': hashlib.sha256(
                world.get_map().to_opendrive().encode()).hexdigest(),
            'turn_arrow_pixels_verified': False,
            'staged_display_kind': 'unofficial_debug_geometry_red_disc_green_right_arrow',
            'staged_display_segments': len(signal_segments()),
            'signal_faces_pedestrian_verified': False,
            'other_device_inventory_verified': False,
            'highway_legal_status_verified': False})
        trigger_sources = ('native-pedestrian-frames.jsonl', 'video_frames.jsonl',
                           'road-boundary.json')
        trigger_hashes = {name: source_digest(output / name) for name in trigger_sources}
        _write_new(output / 'fallback2-path-trigger.json', evaluate_path_trigger(
            output, trigger_hashes, config['walker_speed_mps']))
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
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        for actor, old_state, frozen in original_light_states:
            try:
                actor.set_state(old_state)
                actor.freeze(frozen)
            except BaseException as exc:
                error = error or {'light_restore_error': str(exc)}
        if changed:
            try: restored = restore(client, state)
            except BaseException as exc: error = error or {'world_restore_error': str(exc)}
        _write_new(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'frames': count, 'expected_frames': FRAMES, 'restoration': restored,
            'error': error, 'physical_acceptance_claimed': False,
            'turn_arrow_pixels_verified': False,
            'signal_governance_verified': False,
            'highway_legal_status_verified': False})
    if error:
        raise RuntimeError('Native C228133 attempt failed; inspect capture report')


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
            raise ValueError('Explicit materialized package and owned Native endpoint required')
        execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
