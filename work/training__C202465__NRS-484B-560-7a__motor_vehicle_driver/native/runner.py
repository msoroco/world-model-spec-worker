"""Acquire an original at-grade rail crossing and four-camera vehicle trace."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess

from controller import FRAMES, RATE_HZ, command_target
from source_review import ROLES, load as load_review

ASSIGNMENT = 'training__C202465__NRS-484B-560-7a__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
VARIANTS = ('space_clear', 'space_short', 'grade_clear', 'grade_deficit',
            'trailing_exact', 'trailing_just_short')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(config):
    case = config.get('case_id', '')
    suffix = case.removeprefix(ASSIGNMENT + '__')
    if (case != ASSIGNMENT + '__' + suffix or suffix not in VARIANTS
            or (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('NRS-484B-560-7a', 'C202465', 'motor_vehicle_driver')):
        raise ValueError('Exact rail-crossing case identity differs')
    if config.get('rate_hz') != RATE_HZ or config.get('duration_s') != 30:
        raise ValueError('600 original frames at 20 Hz required')
    if tuple(camera.get('name') for camera in config.get('cameras', [])) != CAMERAS:
        raise ValueError('Four original rail cameras required')
    if config.get('candidate_id') not in ('primary', 'fallback1'):
        raise ValueError('Selected engineering candidate differs')
    if config.get('brake_gain') not in (4.0, 5.0):
        raise ValueError('Declared braking profile required')
    return {'case_id': case, 'frames': FRAMES, 'native_executed': False,
            'physical_acceptance_claimed': False, 'legal_verdict': None}


def footprint(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if not vertices:
        raise ValueError('Original Native body vertices missing')
    return {'min_x_m': min(v.x for v in vertices), 'max_x_m': max(v.x for v in vertices),
            'min_y_m': min(v.y for v in vertices), 'max_y_m': max(v.y for v in vertices)}


def target_x(suffix, far_rail_x, body_length):
    clear = far_rail_x + 4.572 + body_length / 2
    if suffix in ('space_clear', 'grade_clear'):
        return clear + 1.0
    if suffix == 'grade_deficit':
        return clear + 1.0
    if suffix == 'trailing_exact':
        return clear
    if suffix == 'trailing_just_short':
        return clear - 1.0
    raise ValueError('Space-short target must derive from original queue body')


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'rail-actors.jsonl').exists():
        raise ValueError('Fresh materialized Native attempt required')
    review_dir = os.environ.get('C202465_RAIL_REVIEW_DIR')
    if not review_dir:
        raise ValueError('C202465_RAIL_REVIEW_DIR original source prerequisite missing')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    world = client.get_world()
    saved = snapshot(client)
    if saved['settings'].synchronous_mode:
        raise ValueError('Exclusive asynchronous Native world required')
    road = world.get_map().to_opendrive()
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    review = load_review(review_dir, road_sha)
    geometry = review['rail-geometry']
    entry_x = geometry['entry_rail_x_m']
    far_x = geometry['clearance_reference_rail_x_m']
    owned, encoders, camera_queues = [], {}, {}
    changed = False
    completed = 0
    errors = []
    codes = {}
    restoration = {'restored': False}
    failure = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        changed = True
        library = world.get_blueprint_library()
        blueprint = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=entry_x - 30, y=geometry.get('road_center_y_m', 0), z=2),
            carla.Rotation(yaw=0)))
        owned.append(ego)
        if not ego.is_alive:
            raise ValueError('Original Native subject vehicle did not spawn')
        body = footprint(ego)
        body_length = body['max_x_m'] - body['min_x_m']
        if body_length <= 0:
            raise ValueError('Original Native vehicle extent missing')
        (output / 'vehicle-extent.json').write_text(json.dumps({
            'source_kind': 'original_native_vehicle_body', 'actor_id': ego.id,
            'footprint_m': body, 'length_m': body_length}, indent=2) + '\n')
        case_suffix = config['case_id'].removeprefix(ASSIGNMENT + '__')
        target = None if case_suffix == 'space_short' else target_x(case_suffix, far_x, body_length)
        queue_actor = None
        if case_suffix == 'space_short':
            queue_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
            queue_actor = world.spawn_actor(queue_bp, carla.Transform(
                carla.Location(x=far_x + 8.0, y=geometry.get('road_center_y_m', 0), z=2),
                carla.Rotation(yaw=0)))
            queue_actor.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
            owned.append(queue_actor)
            queue_rear_x = footprint(queue_actor)['min_x_m']
            target = queue_rear_x - body_length / 2 - 1.0
            if target >= far_x + 4.572 + body_length / 2:
                raise ValueError('Original queue does not constrain 15-foot trailing clearance')
        (output / 'road.xodr').write_text(road)
        review_out = output / 'rail-review'
        review_out.mkdir(exist_ok=False)
        for role in ROLES:
            for ending in ('.json', '.source.txt'):
                shutil.copy2(Path(review_dir) / (role + ending), review_out / (role + ending))
        mounts = {'overview': (entry_x - 8, -18, 22, -35),
                  'approach': (entry_x - 20, 3, 9, -13),
                  'reference_corner': (far_x + 2, -10, 10, -20),
                  'driver_reference': (far_x + 15, 10, 11, -20)}
        for spec in config['cameras']:
            name = spec['name']
            x, y, z, pitch = mounts[name]
            camera_bp = library.find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', str(spec['width']))
            camera_bp.set_attribute('image_size_y', str(spec['height']))
            camera_bp.set_attribute('fov', str(spec['fov_deg']))
            camera_bp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with PipelineCapture(client, ego, output, config['case_id'],
                             required_observations=config.get('required_atoms', [])) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'rail-actors.jsonl').open('x') as actor_rows, \
                (output / 'trace.jsonl').open('x') as trace_rows:
            initial_time = None
            for index in range(FRAMES):
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.hypot(velocity.x, velocity.y)
                control = command_target(index, pose.location.x, speed, target,
                                         config['brake_gain'])
                ego.apply_control(carla.VehicleControl(
                    throttle=control['throttle'], brake=control['brake'],
                    steer=control['steer']))
                frame = world.tick()
                snapshot_row = world.get_snapshot()
                if snapshot_row.frame != frame:
                    raise ValueError('Original Native frame mismatch')
                if initial_time is None:
                    initial_time = snapshot_row.timestamp.elapsed_seconds
                time_s = snapshot_row.timestamp.elapsed_seconds - initial_time
                camera_frames = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < frame:
                        image = q.get(timeout=30)
                    if image.frame != frame:
                        raise ValueError('Original camera frame mismatch')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = frame
                frame_map.append(frame, time_s, camera_native_frames=camera_frames)
                capture.capture(frame, time_s, extra={'video_frame': index})
                current = ego.get_transform()
                actual = ego.get_velocity()
                queue_body = footprint(queue_actor) if queue_actor else None
                row = {'video_frame': index, 'native_frame': frame, 'time_s': time_s,
                       'vehicle_center_x_m': current.location.x,
                       'observed_speed_mps': math.hypot(actual.x, actual.y),
                       'vehicle_footprint_m': footprint(ego),
                       'vehicle_actor_id': ego.id,
                       'queue_actor_id': queue_actor.id if queue_actor else None,
                       'queue_body_m': queue_body,
                       'source_cameras': {name: index for name in CAMERAS},
                       'camera_native_frames': camera_frames,
                       'stop_cause_source': None,
                       'requested_target_center_x_m': target,
                       'controller_target_source': 'queue_body_collision_avoidance' if queue_actor else 'reviewed_rail_clearance_geometry'}
                actor_rows.write(json.dumps(row) + '\n')
                trace_rows.write(json.dumps({
                    'frame': frame, 'time_s': time_s,
                    'position': {'x': current.location.x, 'y': current.location.y,
                                 'z': current.location.z},
                    'speed_mps': row['observed_speed_mps'],
                    'heading_deg': current.rotation.yaw}) + '\n')
                completed += 1
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            codes[name] = process.wait(timeout=180)
            if codes[name]:
                raise RuntimeError('Original camera encoding failed: ' + name + error.decode()[-300:])
        (output / 'rail-context.json').write_text(json.dumps({
            'source_kind': 'native_rail_vehicle_and_opposite_space_readback',
            'native_map_sha256': sha(output / 'road.xodr'),
            'rail_geometry_sha256': sha(review_out / 'rail-geometry.json'),
            'vehicle_extent_sha256': sha(output / 'vehicle-extent.json'),
            'opposite_space_source_sha256': sha(review_out / 'opposite-space.source.txt'),
            'undercarriage_source_sha256': sha(review_out / 'undercarriage-grade.source.txt'),
            'crossing_kind': geometry['crossing_kind'],
            'road_sha256': road_sha, 'entry_rail_x_m': entry_x,
            'clearance_reference_rail_x_m': far_x,
            'vehicle_length_m': body_length,
            'opposite_side_space_before_entry_m': review['opposite-space']['opposite_side_space_before_entry_m'],
            'minimum_undercarriage_clearance_m': review['undercarriage-grade']['minimum_undercarriage_clearance_m'],
            'rail_grade_required_clearance_m': review['undercarriage-grade']['rail_grade_required_clearance_m'],
            'stop_cause_independently_reviewed': False,
            'physical_acceptance_claimed': False, 'legal_verdict': None}, indent=2) + '\n')
    except BaseException as error:
        failure = error
        errors.append(f'{type(error).__name__}: {error}')
    finally:
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
            try:
                restoration = restore(client, saved)
            except Exception as error:
                errors.append('world restore: ' + str(error))
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': config['case_id'], 'frames': completed, 'errors': errors,
            'restoration': restoration, 'encoder_exit_codes': codes,
            'capture_finished': completed == FRAMES and failure is None,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError('; '.join(errors))
    seal_capture(output, frames=completed, restoration=restoration, errors=errors,
                 encoder_exit_codes=codes,
                 context={'case_id': config['case_id'],
                          'rail_review_source_bound': True,
                          'stop_cause_independently_reviewed': False,
                          'legal_verdict_claimed': False})
    return {'frames': completed, 'original_native_capture': True,
            'physical_acceptance_claimed': False}


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
