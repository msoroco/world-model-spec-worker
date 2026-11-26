"""Original-frame CARLA request for NRS 484B.257(2); no verdict or acceptance.

The CPU checker uses --check without importing CARLA. A live operator supplies a
fresh output directory and a dedicated local server, then independently reviews
road designation, sign obligations, control direction, pixels, and behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from nonthrough_native_construction import constructed_scene
from nonthrough_scene import CAMERAS, request, validate

AID = 'training__C111325__NRS-484B-257-2__motor_vehicle_driver'
RATE = 20
COUNT = 600


def plan():
    return json.loads(Path(__file__).with_name('case-plan.json').read_text())


def scene_for(slug):
    item = next((case for case in plan()['cases'] if case['case_id'] == AID + '__' + slug), None)
    if item is None:
        raise ValueError('Unknown exact 257(2) case')
    scene = request(slug, **item['construction_request'])
    validate(scene)
    return scene


def check():
    cases = plan()['cases']
    summaries = []
    for item in cases:
        slug = item['case_id'].removeprefix(AID + '__')
        scene = scene_for(slug)
        summaries.append({'case_id': item['case_id'], 'reference': scene['stop_reference'],
                          'subject_control': scene['subject_control'],
                          'counterpart_control': scene['counterpart_control'],
                          'exception': scene['control_exception'], 'frames': scene['planned_frames']})
    return {'assignment_id': AID, 'exact_case_count': len(summaries), 'cases': summaries,
            'carla_imported': False, 'physical_acceptance_claimed': False, 'legal_verdict': None}


def xyz(value):
    return [value.x, value.y, value.z]


def speed(value):
    return math.sqrt(value.x ** 2 + value.y ** 2 + value.z ** 2)


def vertices(actor):
    return [xyz(vertex) for vertex in actor.bounding_box.get_world_vertices(actor.get_transform())]


def requested_control(carla, actors, scene, tick):
    ego = actors['ego']
    control = scene['controller']
    body = vertices(ego)
    front = max(point[0] for point in body)
    current = speed(ego.get_velocity())
    action = control['requested_action']
    if action in {'roll_through', 'no_yield'}:
        target = 4.0
    elif tick < control['release_frame']:
        target = max(0.0, min(4.0, (control['reference_front_x_m'] - front) * 1.2))
    else:
        target = 4.0
    error = target - current
    ego.apply_control(carla.VehicleControl(throttle=max(0.0, min(.65, .24 * error)),
                                           brake=max(0.0, min(1.0, -.45 * error)), steer=0.0))
    other = actors['counterpart']
    error = scene['counterpart']['requested_speed_mps'] - speed(other.get_velocity())
    other.apply_control(carla.VehicleControl(throttle=max(0.0, min(.65, .24 * error)),
                                             brake=max(0.0, min(1.0, -.45 * error)), steer=0.0))


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_viewpoint_rays(world, carla, native, time_s):
    """Save a physical ray survey; legal nearest viewpoint stays unresolved."""
    if not callable(getattr(world, 'cast_ray', None)):
        raise ValueError('Original CARLA world lacks cast_ray for viewpoint evidence')
    rows = []
    for front_x in (-15.0, -12.0, -9.0, -6.0, -4.1, -3.8):
        start = carla.Location(x=front_x, y=-1.75, z=1.5)
        for approach_y in (-20.0, -40.0, -80.0):
            end = carla.Location(x=1.75, y=approach_y, z=1.5)
            hits = world.cast_ray(start, end)
            rows.append({'candidate_front_x_m': front_x, 'crossing_target_y_m': approach_y,
                         'start_xyz_m': xyz(start), 'end_xyz_m': xyz(end),
                         'hits': [{'location_xyz_m': xyz(hit.location), 'label': str(hit.label)}
                                  for hit in hits]})
    return {'native_frame': native, 'time_s': time_s, 'rays': rows,
            'nearest_legal_viewpoint_unassessed': True}


def original_control_state(actors, scene, native, time_s):
    """Retain original actor/state facts; legal governing direction needs review."""
    data = {'native_frame': native, 'time_s': time_s,
            'officer_direction_legally_unassessed': True,
            'signal_controls_approach_legally_unassessed': True}
    if scene['control_exception'] == 'police':
        officer = actors.get('officer')
        if officer is None or not officer.is_alive:
            raise ValueError('Original officer actor unavailable')
        pose = officer.get_transform()
        data['officer'] = {'actor_id': officer.id, 'location_xyz_m': xyz(pose.location),
                           'rotation_yaw_deg': pose.rotation.yaw}
    if scene['control_exception'] == 'signal':
        signal = actors.get('signal')
        if signal is None or not signal.is_alive or not callable(getattr(signal, 'get_state', None)):
            raise ValueError('Original governing signal actor/state unavailable')
        data['signal'] = {'actor_id': signal.id, 'state': str(signal.get_state())}
    return data


def capture(slug, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot as world_snapshot, restore as world_restore

    scene = scene_for(slug)
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Retain prior attempt; choose a fresh Native output directory')
    output.mkdir(parents=True, exist_ok=True)
    config_source = Path(__file__).with_name('config.json')
    if config_source.exists():
        (output / 'config.json').write_bytes(config_source.read_bytes())
    client = carla.Client(host, port)
    client.set_timeout(120)
    prior_world = world_snapshot(client)
    encoders = {}
    core = None
    restoration = None
    try:
        with constructed_scene(client, carla, scene) as actors:
            world = actors['world']
            camera_queues = {}
            for spec in scene['cameras']:
                name = spec['name']
                channel = queue.Queue()
                actors['cameras'][name].listen(channel.put)
                camera_queues[name] = channel
                encoders[name] = subprocess.Popen([
                    'ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'bgra',
                    '-video_size', f"{spec['width']}x{spec['height']}", '-framerate', str(RATE),
                    '-i', '-', '-frames:v', str(COUNT), '-c:v', 'ffv1', str(output / (name + '.mkv'))],
                    stdin=subprocess.PIPE)
            core = PipelineCapture(client, actors['ego'], output, AID + '__' + slug,
                                   required_observations=[])
            first_elapsed = None
            samples = []
            sight_rows = []
            control_rows = []
            for i in range(COUNT):
                requested_control(carla, actors, scene, i)
                native = world.tick()
                snapshot = world.get_snapshot()
                if native != snapshot.frame:
                    raise RuntimeError('Native tick/snapshot identity differs')
                if first_elapsed is None:
                    first_elapsed = snapshot.timestamp.elapsed_seconds
                time_s = snapshot.timestamp.elapsed_seconds - first_elapsed
                if abs(time_s - i / RATE) > .005:
                    raise RuntimeError('Original 20 Hz elapsed-time join differs')
                ego, other = actors['ego'], actors['counterpart']
                ego_body, other_body = vertices(ego), vertices(other)
                ego_front = max(point[0] for point in ego_body)
                other_front = max(point[1] for point in other_body)
                cameras = {}
                rgb_hashes = {}
                for name, channel in camera_queues.items():
                    image = channel.get(timeout=30)
                    if image.frame != native:
                        raise RuntimeError('Source camera frame differs from Native tick: ' + name)
                    cameras[name] = image.frame
                    rgb_hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                    encoders[name].stdin.write(image.raw_data)
                core.capture(native, time_s, extra={'nonthrough_counterpart': {
                    'actor_id': other.id, 'position_m': xyz(other.get_location()),
                    'velocity_mps': xyz(other.get_velocity())}})
                if scene['stop_reference'] == 'nearest_viewpoint':
                    sight_rows.append(original_viewpoint_rays(world, carla, native, time_s))
                if scene['control_exception'] is not None:
                    control_rows.append(original_control_state(actors, scene, native, time_s))
                samples.append({
                    'frame': i, 'native_frame': native, 't_s': i / RATE,
                    'subject_id': ego.id, 'counterpart_id': other.id,
                    'subject_body_vertices_m': ego_body, 'counterpart_body_vertices_m': other_body,
                    'subject_speed_mps': speed(ego.get_velocity()),
                    'counterpart_speed_mps': speed(other.get_velocity()),
                    'subject_front_before_reference': ego_front < control_reference(scene),
                    'subject_inside': ego_front >= -3.5 and min(v[0] for v in ego_body) <= 3.5,
                    'counterpart_inside': other_front >= -3.5 and min(v[1] for v in other_body) <= 3.5,
                    'counterpart_distance_to_conflict_m': max(0.0, -3.5 - other_front),
                    'officer_controlling': False, 'signal_controlling': False,
                    'control_direction_legally_unassessed': True,
                    'source_cameras': cameras, 'camera_rgb_sha256': rgb_hashes,
                })
            for process in encoders.values():
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError('Source camera encoder failed')
            for name in camera_queues:
                decoded = subprocess.run([
                    'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                    '-show_entries', 'stream=nb_read_frames', '-of', 'default=nokey=1:noprint_wrappers=1',
                    str(output / (name + '.mkv'))], check=True, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
                if decoded.stdout.strip() != str(COUNT):
                    raise RuntimeError('Source camera decoded frame count differs: ' + name)
            core.close(confirmed=True)
            core = None
            map_path = output / 'road.xodr'
            controls = {'assignment_id': AID, 'source_kind': 'native_saved_sample',
                        'road_kind': 'non_through_highway',
                        'road_kind_independent_review_required': True,
                        'subject_control': scene['subject_control'] + '_sign',
                        'counterpart_control': scene['counterpart_control'] + '_sign'
                        if scene['counterpart_control'] != 'none' else 'none',
                        'entrance_controls': {key: value + '_sign' if value != 'none' else 'none'
                                              for key, value in scene['entrance_control_inventory_requested'].items()},
                        'subject_entrance_sign_governs': True,
                        'entrance_control_independent_review_required': True,
                        'stop_reference': scene['stop_reference'],
                        'control_exception': scene['control_exception'],
                        'control_direction_independent_review_required': scene['control_exception'] is not None,
                        'map_readback_sha256': sha(map_path)}
            if sight_rows:
                write_json(output / 'viewpoint_sight_rays.json', sight_rows)
                controls['viewpoint_sight_rays_sha256'] = sha(output / 'viewpoint_sight_rays.json')
            if control_rows:
                write_json(output / 'control_state_frames.json', control_rows)
                controls['control_state_frames_sha256'] = sha(output / 'control_state_frames.json')
            write_json(output / 'entrance_controls.json', controls)
            (output / 'video_frames.jsonl').write_text(''.join(json.dumps({
                'video_frame': row['frame'], 'carla_frame': row['native_frame'],
                'native_frame': row['native_frame'], 'time_s': row['t_s'],
                'source_cameras': row['source_cameras'],
                'camera_rgb_sha256': row['camera_rgb_sha256']}, allow_nan=False) + '\n'
                for row in samples))
            write_json(output / 'nonthrough_saved_packet.json', {
                'assignment_id': AID, 'source_kind': 'native_saved_sample',
                'subject_id': actors['ego'].id, 'counterpart_id': actors['counterpart'].id,
                'frames': samples})
            write_json(output / 'acquisition-provenance.json', {
                'provenance_kind': 'native', 'native_executed': True,
                'diagnostic_fixture': False, 'physical_acceptance_claimed': False})
        restoration = world_restore(client, prior_world)
        seal_capture(output, frames=COUNT, restoration=restoration, errors=[],
                     encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                     context={'case_id': AID + '__' + slug, 'original_native_readback': True,
                              'legal_verdict': None, 'physical_acceptance_claimed': False})
        return {'case_id': AID + '__' + slug, 'source_frames': COUNT,
                'original_capture_saved': True, 'physical_acceptance_claimed': False,
                'legal_verdict': None}
    except BaseException as error:
        if core is not None:
            try:
                core.close(confirmed=False)
            except BaseException as close_error:
                error = RuntimeError('Native recorder closure also failed: ' + str(close_error))
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
        if restoration is None:
            try:
                restoration = world_restore(client, prior_world)
            except BaseException as restore_error:
                error = RuntimeError('Native world restoration also failed: ' + str(restore_error))
        write_json(output / 'native-run-status.json', {'capture_failed': True,
                   'error_type': type(error).__name__, 'message': str(error),
                   'physical_acceptance_claimed': False})
        raise error


def control_reference(scene):
    return scene['controller']['reference_front_x_m']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        if not args.case or not args.output_dir:
            parser.error('Native capture requires --case and --output-dir')
        print(json.dumps(capture(args.case, args.output_dir, args.host, args.port), sort_keys=True))
