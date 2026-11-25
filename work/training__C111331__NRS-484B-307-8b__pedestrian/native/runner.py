"""Native red-entry construction. ``--check`` is CPU-only and imports no CARLA.

Original readback and pixels are retained. A surveyed OpenDRIVE identity does
not itself establish official status, pedestrian governance, or legal outcome.
"""

import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import traceback
from types import SimpleNamespace

from native_red import (CAMERAS, FRAMES, RATE_HZ, OTHER_OD_ID, check_plan,
                        command_countdown_head, configure_heads, measure_entry,
                        requested_speed, resolve_heads, sample_heads)
from source_join import audit_attempt

HERE = Path(__file__).resolve().parent


class WalkerCaptureAdapter:
    """Expose a vehicle-shaped control snapshot to the shared trace recorder.

    The underlying actor remains the original walker; only the control schema
    is adapted for PipelineCapture's common trace fields.
    """

    def __init__(self, walker):
        self.walker = walker

    def __getattr__(self, name):
        return getattr(self.walker, name)

    def get_control(self):
        control = self.walker.get_control()
        return SimpleNamespace(throttle=0.0, steer=0.0,
                               brake=0.0, hand_brake=False, reverse=False,
                               manual_gear_shift=False, gear=0,
                               walker_speed_mps=float(control.speed),
                               walker_direction_xyz=[control.direction.x,
                                                     control.direction.y,
                                                     control.direction.z])


def _new_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def _footprint(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
    if len(points) != 4:
        raise ValueError('Original pedestrian ground footprint incomplete')
    return [list(point) for point in points]


def _camera_rgb(image, width, height, np):
    return np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
        height, width, 4)[:, :, :3][:, :, ::-1].tobytes()


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap, seal_capture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check_plan(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Exact fresh materialized attempt required')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior_world = client.get_world()
    previous = snapshot(client)
    if previous['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in prior_world.get_actors()):
        raise ValueError('Exclusive idle asynchronous Native world required')
    owned, camera_queues, encoders, encoder_logs, encoder_exit = [], {}, {}, {}, {}
    capture = None
    changed = False
    error = None
    restored = None
    rows = []
    frames = 0
    try:
        world = client.generate_opendrive_world(
            (HERE / 'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=True))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        library = world.get_blueprint_library()
        heads = resolve_heads(world.get_actors())
        configure_heads(heads, config, carla)
        blueprints = sorted(library.filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        if not blueprints:
            raise ValueError('Native pedestrian blueprint absent')
        walker = world.try_spawn_actor(blueprints[0], carla.Transform(
            carla.Location(x=config['walker_start_xy_m'][0],
                           y=config['walker_start_xy_m'][1], z=.5),
            carla.Rotation(yaw=-90)))
        if walker is None:
            raise ValueError('Native pedestrian spawn failed')
        owned.append(walker)
        for name, width, height, pose in CAMERAS:
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            x, y, z, yaw, pitch = pose
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z),
                carla.Rotation(yaw=yaw, pitch=pitch)))
            if sensor is None:
                raise ValueError('Native camera spawn failed: ' + name)
            owned.append(sensor)
            camera_queues[name] = queue.Queue()
            sensor.listen(camera_queues[name].put)
            encoder_logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', str(RATE_HZ), '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=encoder_logs[name])
        capture = PipelineCapture(client, WalkerCaptureAdapter(walker), output, config['case_id'],
                                  visibility=False,
                                  required_observations=config.get('required_atoms', []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'red-entry-original.jsonl').open('x') as original, \
                (output / 'camera-sources.jsonl').open('x') as cameras:
            for index in range(FRAMES):
                walker.apply_control(carla.WalkerControl(
                    direction=carla.Vector3D(x=0, y=-1),
                    speed=requested_speed(config['condition'], index)))
                program = None
                if config['condition'] == 'exception_countdown':
                    program = command_countdown_head(heads[OTHER_OD_ID], carla, index)
                    if program['flashing'] and program['illuminated']:
                        world.debug.draw_string(
                            carla.Location(x=9.0, y=4.5, z=2.5),
                            "DON'T WALK " + str(program['countdown_seconds']),
                            draw_shadow=False,
                            color=carla.Color(r=240, g=90, b=40),
                            life_time=.06, persistent_lines=False)
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                observed = sample_heads(heads)
                pose = walker.get_transform().location
                person = {'video_frame': index, 'native_frame': frame,
                          'time_s': time_s, 'walker_id': walker.id,
                          'center_xy_m': [pose.x, pose.y],
                          'footprint_xy_m': _footprint(walker),
                          'traffic': observed['traffic'],
                          'other': observed['other'],
                          'display_program': program,
                          'requested_entry': config['requested_entry'],
                          'authority_review_pending': True,
                          'pixel_review_pending': True}
                capture.capture(frame, time_s, extra={'red_entry_source': person})
                pixels = {}
                for name, width, height, _ in CAMERAS:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise ValueError('Original camera/Native frame join differs')
                    rgb = _camera_rgb(image, width, height, np)
                    pixels[name] = hashlib.sha256(rgb).hexdigest()
                    encoders[name].stdin.write(rgb)
                    cameras.write(json.dumps({
                        'camera': name, 'video_frame': index,
                        'native_frame': frame, 'time_s': time_s,
                        'width': width, 'height': height,
                        'source_path': name + '.mkv',
                        'source_rgb_sha256': pixels[name]}, allow_nan=False) + '\n')
                person['source_rgb_sha256'] = pixels
                original.write(json.dumps(person, allow_nan=False) + '\n')
                frame_map.append(frame, time_s, source_rgb_sha256=pixels)
                rows.append(person)
                frames += 1
        measured = measure_entry(rows, config)
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
        measured = None
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                encoder_exit[name] = encoder.wait(timeout=180)
                if encoder_exit[name] != 0:
                    raise ValueError('Lossless camera encoder failed: ' + name)
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
            try:
                restored = restore(client, previous)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        _new_json(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'frames': frames,
            'expected_frames': FRAMES, 'restoration': restored,
            'error': error, 'measured': measured,
            'governing_head_reviewed': False,
            'actual_pixels_reviewed': False,
            'physical_completion_verified': False,
            'legal_verdict': None})
    if error:
        raise RuntimeError('Native red-entry capture failed; see native-capture-report.json')
    seal_capture(output, frames=frames, restoration=restored, errors=[],
                 encoder_exit_codes=encoder_exit,
                 context={'red_entry': measured, 'physical_acceptance_claimed': False})
    _new_json(output / 'original-source-audit.json', audit_attempt(output, config))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default='2000')
    args = parser.parse_args()
    config = json.loads((HERE / 'config.json').read_text())
    if args.check:
        print(json.dumps(check_plan(config), sort_keys=True))
        return
    if not args.output_dir:
        raise ValueError('--output-dir required for Native capture')
    execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
