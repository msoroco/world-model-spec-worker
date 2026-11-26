"""Original Native stop/deceleration and rear-signal capture; --check is CPU only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from layout import check as layout_check, open_drive

FRAMES = 600
CAMERAS = (
    ('overview', 1920, 1080, 30, -22, 23, -60),
    ('approach', 1280, 720, -42, -10, 9, -25),
    ('reference_corner', 1280, 720, 24, 9, 9, -30),
    ('driver_reference', 1280, 720, 42, 8, 9, -30),
)
SUFFIXES = ('witness_1', 'witness_2', 'decrease_early', 'decrease_late')


def is_early(suffix):
    return suffix in ('witness_1', 'decrease_early')


def is_stop(suffix):
    return suffix in ('witness_1', 'witness_2')


def check():
    config = json.loads(Path('config.json').read_text())
    if config['cell_id'] != 'C179480' or config['law_id'] != 'NRS-484B-413-3':
        raise ValueError('Exact frozen law/cell differs')
    if config['case_suffix'] not in SUFFIXES or config['case_id'] != (
            'training__C179480__NRS-484B-413-3__motor_vehicle_driver__'
            + config['case_suffix']):
        raise ValueError('Selected case differs')
    if config['duration_s'] != 30 or config['rate_hz'] != 20 or config['frames'] != FRAMES:
        raise ValueError('Frame policy differs')
    if [(c['name'], c['width'], c['height']) for c in config['cameras']] != [
            (name, width, height) for name, width, height, *_ in CAMERAS]:
        raise ValueError('Four camera profile differs')
    expected_signal = (100 if is_early(config['case_suffix']) else
                       160 if is_stop(config['case_suffix']) else 121)
    if config['action_frame'] != 120 or config['signal_command_frame'] != expected_signal:
        raise ValueError('Controlled signal-time variable differs')
    return {'passed': True, 'layout': layout_check(), 'frame_count': FRAMES,
            'native_imported': False, 'physical_acceptance_claimed': False}


def actor_source(actor, mapping, carla):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    acceleration = actor.get_acceleration()
    waypoint = mapping.get_waypoint(pose.location, project_to_road=True,
                                    lane_type=carla.LaneType.Driving)
    return {'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'center_xy_m': [pose.location.x, pose.location.y],
            'body_xy_m': [[p.x, p.y] for p in actor.bounding_box.get_world_vertices(pose)],
            'lane_id': waypoint.lane_id if waypoint is not None else None,
            'speed_mps': math.hypot(velocity.x, velocity.y),
            'acceleration_x_mps2': acceleration.x}


def requested_speed(suffix, frame):
    if frame < 120:
        return 8.0
    elapsed = frame - 120
    if is_stop(suffix):
        return max(0.0, 8.0 - elapsed * 8.0 / 30.0)
    return max(4.0, 8.0 - elapsed * 4.0 / 12.0)


def execute(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import snapshot, restore

    config = json.loads(Path('config.json').read_text())
    check()
    output = Path(output).resolve()
    if output.exists() and any((output / name).exists() for name in
            ('actor-sources.jsonl', 'camera-frames.jsonl', 'native-exit.json', 'result.json')):
        raise ValueError('Original Native output must be fresh')
    client = carla.Client(host, port)
    client.set_timeout(180)
    old = client.get_world()
    saved = snapshot(client)
    if old.get_settings().synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    output.mkdir(parents=True, exist_ok=True)
    owned = []
    encoders = {}
    camera_queues = {}
    encoder_exits = {}
    changed = False
    capture = None
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=50, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        mapping = world.get_map()
        for x in (-36, -20, 24):
            waypoint = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1),
                                            project_to_road=True, lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != -1:
                raise RuntimeError('Native shared-lane readback failed')
        blueprints = world.get_blueprint_library()
        ego = world.try_spawn_actor(blueprints.find('vehicle.tesla.model3'),
                                    carla.Transform(carla.Location(x=-20, y=-1.75, z=1.2),
                                                    carla.Rotation(yaw=0)))
        rear = world.try_spawn_actor(blueprints.find('vehicle.audi.tt'),
                                     carla.Transform(carla.Location(x=-36, y=-1.75, z=1.2),
                                                     carla.Rotation(yaw=0)))
        if ego is None or rear is None:
            raise RuntimeError('Original ego/rear actor spawn failed')
        owned.extend((ego, rear))
        for name, width, height, x, y, z, pitch in CAMERAS:
            camera_bp = blueprints.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 85), ('sensor_tick', .05)):
                camera_bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(camera_bp,
                                       carla.Transform(carla.Location(x=x, y=y, z=z),
                                                       carla.Rotation(pitch=pitch)))
            owned.append(sensor)
            received = queue.Queue()
            sensor.listen(received.put)
            camera_queues[name] = received
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', '20', '-i', '-', '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  required_observations=[])
        with (output / 'actor-sources.jsonl').open('x') as actor_rows, \
                (output / 'camera-frames.jsonl').open('x') as image_rows, \
                FrameMap(output / 'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                speed = requested_speed(config['case_suffix'], index)
                ego.set_target_velocity(carla.Vector3D(x=speed, y=0, z=0))
                rear.set_target_velocity(carla.Vector3D(x=speed, y=0, z=0))
                lamp_commanded = index >= config['signal_command_frame']
                ego.set_light_state(carla.VehicleLightState.Brake if lamp_commanded
                                    else carla.VehicleLightState.NONE)
                native_frame = world.tick()
                ego_source = actor_source(ego, mapping, carla)
                rear_source = actor_source(rear, mapping, carla)
                brake_state = ego.get_light_state()
                rear_body_max_x = max(p[0] for p in rear_source['body_xy_m'])
                ego_body_min_x = min(p[0] for p in ego_source['body_xy_m'])
                row = {'case_id': config['case_id'], 'frame': index, 'native_frame': native_frame,
                       'time_s': index / 20, 'source_kind': 'original_native',
                       'ego': ego_source, 'rear': rear_source,
                       'ego_lane_id': ego_source['lane_id'],
                       'rear_lane_id': rear_source['lane_id'],
                       'rear_is_behind': rear_source['center_xy_m'][0] < ego_source['center_xy_m'][0],
                       'surface_gap_m': ego_body_min_x - rear_body_max_x,
                       'ego_speed_mps': ego_source['speed_mps'],
                       'ego_accel_longitudinal_mps2': ego_source['acceleration_x_mps2'],
                       'brake_lamp_commanded': lamp_commanded,
                       'brake_lamp_observed': bool(brake_state & carla.VehicleLightState.Brake),
                       'hand_signal': 'none'}
                actor_rows.write(json.dumps(row, allow_nan=False) + '\n')
                capture.capture(native_frame, index / 20, extra={'c179480_rear_signal': row})
                camera_native_frames = {}
                for name, *_ in CAMERAS:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original four-camera join differs')
                    encoders[name].stdin.write(image.raw_data)
                    image_rows.write(json.dumps({'frame': index, 'camera': name,
                        'native_frame': native_frame,
                        'rgb_sha256': hashlib.sha256(image.raw_data).hexdigest()}) + '\n')
                    camera_native_frames[name] = image.frame
                frame_map.append(native_frame, index / 20,
                                 camera_native_frames=camera_native_frames)
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_exits[name] = process.wait(timeout=180)
            if encoder_exits[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original FFV1 encoding failed: ' + name + error.decode()[-400:])
        capture.close(confirmed=True)
        capture = None
        (output / 'road.xodr').write_text(open_drive())
        (output / 'rear-signal-context.json').write_text(json.dumps({
            'source_kind': 'original_native', 'cell_id': 'C179480',
            'public_highway_reviewed': False, 'immediate_rear_reviewed': False,
            'signal_appropriateness_reviewed': False,
            'legal_suddenness_reviewed': False, 'hand_signal_observed': False,
            'diagnostic_deceleration_mps2': 3.0,
            'diagnostic_bound_is_statutory': False}, indent=2) + '\n')
        return {'frames': FRAMES, 'camera_names': list(camera_queues),
                'original_native_executed': True, 'legal_verdict_claimed': False}
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restored = restore(client, saved)
            if capture is None and len(encoder_exits) == 4:
                seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                             encoder_exit_codes=encoder_exits,
                             context={'case_id': config['case_id']})
                record_native_exit(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        if args.output_dir is None:
            parser.error('Original Native output directory required')
        print(json.dumps(execute(args.output_dir, args.host, args.port)))
