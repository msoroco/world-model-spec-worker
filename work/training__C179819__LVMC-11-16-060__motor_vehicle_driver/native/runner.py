"""Original Native speed and sign-survey acquisition draft; no legal verdict."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from controller import FRAMES, RATE_HZ, TARGET_MPH, command
from geometry import check as geometry_check, open_drive

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CASES = {'probe_1': 'slow', 'probe_2': 'at_default', 'probe_3': 'fast',
         'posted_35': 'posted_35'}


def check(config):
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C179819', 'LVMC-11-16-060', 'motor_vehicle_driver'):
        raise ValueError('exact assignment identity changed')
    suffix = config['case_id'].rsplit('__', 1)[-1]
    if suffix not in CASES or config['speed_case'] != CASES[suffix]:
        raise ValueError('unknown exact speed comparison case')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != FRAMES / RATE_HZ:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four original source cameras required')
    return {'geometry': geometry_check(), 'frames': FRAMES,
            'camera_names': CAMERAS, 'requested_speed_mph': TARGET_MPH[config['speed_case']],
            'native_imported': False, 'street_authority_sourced': False,
            'legal_outcome_claimed': False}


def survey(carla, mapping):
    rows = []
    for x in (-50, 0, 100, 200, 300, 400, 500):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-2, z=1.4),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1 or abs(wp.transform.location.x - x) > 1:
            raise RuntimeError('Native roadway survey failed')
        rows.append({'x_m': x, 'road_id': wp.road_id, 'lane_id': wp.lane_id})
    return rows


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'actor-poses.jsonl').exists():
        raise ValueError('new materialized attempt required')
    (output / 'law-text.json').write_text(json.dumps({'source': 'LVMC 11.16.060',
        'text': config['statutory_text']}, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('exclusive idle Native world required')
    owned, encoders, queues = [], {}, {}
    capture = None
    changed = False
    complete = False
    try:
        world = client.generate_opendrive_world(open_drive(config.get('posted_limit_mph')), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        readback = survey(carla, world.get_map())
        library = world.get_blueprint_library()
        bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        bp.set_attribute('role_name', 'c179819_subject')
        subject = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=-50, y=-2, z=2), carla.Rotation(yaw=0)))
        owned.append(subject)
        capture = PipelineCapture(client, subject, output, config['case_id'],
                                  visibility=False,
                                  required_observations=config.get('required_atoms', []))
        (output / 'sign-survey-native.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'lane_survey': readback,
            'street_status': 'unverified', 'survey_complete_both_directions': False,
            'applicable_posted_signs': [], 'sign_authority_source': None,
            'map_landmarks': [{'id': str(item.id), 'name': getattr(item, 'name', ''),
                               'value': getattr(item, 'value', None)}
                              for item in world.get_map().get_all_landmarks()],
            'subject_blueprint_id': subject.type_id}, indent=2) + '\n')
        mounts = {'overview': (-25, -20, 35, -35), 'approach': (1.5, 0, 1.8, 0),
                  'reference_corner': (90, -9, 9, -15), 'driver_reference': (-6, 0, 3, -5)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            cbp = library.find('sensor.camera.rgb')
            cbp.set_attribute('image_size_x', str(spec['width']))
            cbp.set_attribute('image_size_y', str(spec['height']))
            cbp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            transform = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch))
            camera = world.spawn_actor(cbp, transform, attach_to=subject if name in ('approach', 'driver_reference') else None)
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'actor-poses.jsonl').open('x') as poses:
            initial_time = None
            for index in range(FRAMES):
                velocity = subject.get_velocity()
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                request = command(config['speed_case'], index, speed)
                subject.apply_control(carla.VehicleControl(
                    throttle=request['throttle'], brake=request['brake'], steer=request['steer']))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                capture.capture(native_frame, time_s)
                camera_frames = {}
                for name, q in queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                pose = subject.get_transform()
                observed = subject.get_velocity()
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'subject_id': subject.id,
                    'route_position_m': pose.location.x,
                    'subject_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
                    'observed_speed_mps': math.sqrt(observed.x ** 2 + observed.y ** 2 + observed.z ** 2),
                    'requested_control': request, 'camera_native_frames': camera_frames,
                    'source_cameras': {name: index for name in CAMERAS}}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        complete = True
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'sign_authority_sourced': False, 'legal_outcome_claimed': False}
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
        if changed:
            restore(client, saved)


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
