"""Original Native taxi stand departure capture; requires local CARLA ownership."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from controller import FRAMES, RATE_HZ, command
from geometry import check as geometry_check, open_drive

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CASES = {'probe_01': 'right', 'probe_02': 'straight'}


def check(config):
    suffix = config['case_id'].rsplit('__', 1)[-1]
    if (config['law_id'], config['cell_id'], config['actor']) != (
            'LVMC-11-60-090', 'C110875', 'taxi_driver'):
        raise ValueError('Wrong taxi law, cell, or actor')
    if suffix not in CASES or config['requested_first_turn'] != CASES[suffix]:
        raise ValueError('Unknown first-turn comparison')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != FRAMES / RATE_HZ:
        raise ValueError('Recording contract changed')
    if tuple(camera['name'] for camera in config['cameras']) != CAMERAS:
        raise ValueError('Four source cameras required')
    if [(c['width'], c['height']) for c in config['cameras']] != [
            (1920, 1080), (1280, 720), (1280, 720), (1280, 720)]:
        raise ValueError('Camera profile changed')
    return {'geometry': geometry_check(), 'frames': FRAMES,
            'requested_first_turn': CASES[suffix], 'native_imported': False,
            'stand_and_notice_authority_verified': False,
            'physical_completion_claimed': False}


def _survey(carla, mapping):
    points = []
    for x in (5, 10, 40, 75, 79, 81, 100, 125, 130, 131):
        waypoint = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1.4),
            project_to_road=True, lane_type=carla.LaneType.Driving)
        if waypoint is None or abs(waypoint.transform.location.x - x) > 2:
            raise RuntimeError('Native approach or second-street waypoint absent')
        points.append({'x_m': x, 'road_id': waypoint.road_id,
                       'lane_id': waypoint.lane_id,
                       'junction': waypoint.is_junction})
    if not points[4]['junction'] or not points[8]['junction']:
        raise RuntimeError('First/later Native junction readback absent')
    return points


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'actor-poses.jsonl').exists():
        raise ValueError('New exact-case attempt directory required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in prior_world.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned, encoders, queues = [], {}, {}
    capture = None
    changed = complete = False
    try:
        world = client.generate_opendrive_world(open_drive(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=10, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        readback = _survey(carla, world.get_map())
        library = world.get_blueprint_library()
        candidates = sorted(library.filter('vehicle.*'), key=lambda bp: bp.id)
        if not candidates:
            raise RuntimeError('Native vehicle blueprint missing')
        blueprint = candidates[0]
        blueprint.set_attribute('role_name', 'c110875_taxi_subject')
        subject = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=5, y=-1.75, z=2), carla.Rotation(yaw=0)))
        owned.append(subject)
        capture = PipelineCapture(client, subject, output, config['case_id'],
            visibility=False, required_observations=config.get('required_atoms', []))
        (output / 'route-survey-native.json').write_text(json.dumps({
            'source_kind': 'original_native', 'roadway_readback': readback,
            'map_landmarks': [{'id': str(item.id),
                'name': getattr(item, 'name', ''),
                'value': getattr(item, 'value', None)}
                for item in world.get_map().get_all_landmarks()],
            'subject_blueprint_id': subject.type_id,
            'taxi_license_source': None,
            'stand_designation_authority_source': None,
            'posted_notice_authority_source': None,
            'first_street_identity_review': 'pending',
            'legal_verdict': None}, indent=2) + '\n')
        mounts = {'overview': (45, -28, 35, -35),
                  'approach': (1.5, 0, 1.8, 0),
                  'reference_corner': (75, -12, 9, -15),
                  'driver_reference': (-5, 0, 3, -5)}
        for name in CAMERAS:
            spec = next(c for c in config['cameras'] if c['name'] == name)
            x, y, z, pitch = mounts[name]
            sensor_blueprint = library.find('sensor.camera.rgb')
            sensor_blueprint.set_attribute('image_size_x', str(spec['width']))
            sensor_blueprint.set_attribute('image_size_y', str(spec['height']))
            sensor_blueprint.set_attribute('sensor_tick', str(1 / RATE_HZ))
            sensor_blueprint.set_attribute('fov', str(spec['fov_deg']))
            sensor = world.spawn_actor(sensor_blueprint,
                carla.Transform(carla.Location(x=x, y=y, z=z),
                    carla.Rotation(pitch=pitch)),
                attach_to=subject if name in ('approach', 'driver_reference') else None)
            owned.append(sensor)
            frame_queue = queue.Queue()
            sensor.listen(frame_queue.put)
            queues[name] = frame_queue
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'actor-poses.jsonl').open('x') as poses, \
                (output / 'trace.jsonl').open('x') as trace:
            initial_time = None
            for index in range(FRAMES):
                before = subject.get_transform()
                velocity = subject.get_velocity()
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                requested = command(config['requested_first_turn'],
                    before.location.x, before.location.y, before.rotation.yaw,
                    speed, gain=config.get('steering_gain', .018))
                subject.apply_control(carla.VehicleControl(
                    throttle=requested['throttle'], brake=requested['brake'],
                    steer=requested['steer']))
                native_frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot mismatch')
                if initial_time is None:
                    initial_time = snapshot.timestamp.elapsed_seconds
                time_s = snapshot.timestamp.elapsed_seconds - initial_time
                capture.capture(native_frame, time_s)
                camera_frames = {}
                for name, frame_queue in queues.items():
                    image = frame_queue.get(timeout=30)
                    while image.frame < native_frame:
                        image = frame_queue.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s,
                    camera_native_frames=camera_frames)
                pose = subject.get_transform()
                velocity = subject.get_velocity()
                observed_speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                row = {'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'subject_id': subject.id,
                    'subject_blueprint_id': subject.type_id,
                    'subject_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
                    'heading_deg': pose.rotation.yaw,
                    'observed_speed_mps': observed_speed,
                    'requested_control': requested,
                    'camera_native_frames': camera_frames,
                    'source_cameras': {name: index for name in CAMERAS}}
                poses.write(json.dumps(row) + '\n')
                trace.write(json.dumps({'frame': native_frame, 'time_s': time_s,
                    'position': {'x': pose.location.x, 'y': pose.location.y,
                                 'z': pose.location.z},
                    'heading_deg': pose.rotation.yaw,
                    'speed_mps': observed_speed}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Camera encode failed: ' + name + ': ' + error.decode()[-300:])
        complete = True
        return {'frames': FRAMES, 'cameras': list(CAMERAS),
                'stand_and_sign_authority_verified': False,
                'physical_acceptance_claimed': False}
    finally:
        if capture is not None:
            capture.close(confirmed=complete)
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
        restoration = restore(client, saved) if changed else {'restored': True,
            'world_unchanged': True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                context={'case_id': config['case_id'],
                         'candidate_id': config.get('candidate_id', 'primary'),
                         'stand_notice_license_review': 'pending'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required')
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
