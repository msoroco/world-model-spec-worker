"""Exact C102951 Native request validation and source-preserving CARLA attempt.

--check is CPU-only. Execution requires an exclusive idle CARLA server and creates
an unaccepted capture; driver-eye visibility still needs source-backed review.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

AID = 'training__C102951__NRS-484B-213-1__motor_vehicle_driver'
HERE = Path(__file__).resolve().parent


def repository():
    for parent in (HERE, *HERE.parents):
        if (parent/'batch.json').is_file() and (parent/'runtime').is_dir():
            return parent
    override = os.environ.get('SCENARIO_REPO_ROOT')
    if override and (Path(override)/'runtime').is_dir():
        return Path(override).resolve()
    raise ValueError('Pinned runtime repository unavailable')


ROOT = repository()
CASE = ROOT/'work'/AID


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle, distance, candidate):
    bundle = Path(bundle)
    if distance not in (70, 120, 170) or candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown exact C102951 case or candidate')
    config = json.loads((bundle/'config.json').read_text())
    expected = {'case_id': AID+'__'+str(distance), 'candidate_id': candidate,
                'distance_m': distance, 'cell_id': 'C102951',
                'law_id': 'NRS-484B-213-1', 'actor': 'motor_vehicle_driver',
                'rate_hz': 20, 'duration_s': 24,
                'status': 'unselected_native_request'}
    if config.get('format') != 'c102951-native-request-v1' or any(
            config.get(key) != value for key, value in expected.items()):
        raise ValueError('Exact passing configuration differs')
    canonical = bundle.resolve() == (HERE/'drafts'/str(distance)/candidate).resolve()
    road = HERE/'road.xodr' if canonical else bundle/'road.xodr'
    assignment = ROOT/'inputs'/AID/'assignment.json' if canonical else bundle/'assignment-source.json'
    plan = CASE/'case-plan.json' if canonical else bundle/'case-plan.json'
    sources = {'road_sha256': road, 'assignment_sha256': assignment,
               'case_plan_sha256': plan,
               'tracks_sha256': bundle/'requested-tracks.jsonl'}
    if any(sha(path) != config.get(key) for key, path in sources.items()):
        raise ValueError('Frozen or authored passing source hash differs')
    lanes = {int(l.attrib['id']): l.attrib['type'] for l in ET.parse(road).findall('.//lane')}
    if lanes != {-1: 'driving', 0: 'none', 1: 'driving'}:
        raise ValueError('Two opposing Native lanes absent')
    rows = [json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows) != 480:
        raise ValueError('Passing request frame count differs')
    for i, row in enumerate(rows):
        if (row.get('frame') != i or abs(row.get('time_s', -1)-i/20) > 1e-6 or
                row.get('source_kind') != 'authored_native_request' or
                row.get('ego_blueprint_request') != 'vehicle.tesla.model3' or
                row.get('requested_entry_oncoming_body_gap_m') != distance or
                row.get('requested_driver_eye_clear_m') != distance or
                row.get('sightline_assumed_visible') is not True):
            raise ValueError('Passing request frame or provenance differs')
    return {'passed': True, 'case_id': expected['case_id'],
            'candidate_id': candidate, 'requested_frames': 480,
            'carla_imported': False, 'original_native_observed': False,
            'physical_or_legal_outcome_claimed': False}


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def pose_record(actor):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(pose)
    return {'actor_id': actor.id, 'blueprint': actor.type_id,
            'center_native_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
            'yaw_deg': pose.rotation.yaw,
            'velocity_native_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'speed_mps': math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
            'body_native_xyz_m': [[v.x, v.y, v.z] for v in vertices]}


def steering(carla, actor, xy, target_speed):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    dx, dy = xy[0]-pose.location.x, xy[1]-pose.location.y
    error = math.atan2(dy, dx)-math.radians(pose.rotation.yaw)
    error = math.atan2(math.sin(error), math.cos(error))
    steer = max(-.75, min(.75, 1.8*error))
    throttle = max(0, min(1, .2+.25*(target_speed-speed)))
    brake = max(0, min(1, .35*(speed-target_speed)))
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer)


def execute(bundle, distance, candidate, output, host, port):
    check(bundle, distance, candidate)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Native output must be a fresh directory')
    output.mkdir(parents=True)
    sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0, str(ROOT/'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    bundle = Path(bundle)
    config = json.loads((bundle/'config.json').read_text())
    requests = [json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    road = HERE/'road.xodr' if bundle.resolve() == (HERE/'drafts'/str(distance)/candidate).resolve() else bundle/'road.xodr'
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned, video, logs, camera_queues = [], {}, {}, {}
    capture, changed, frames, restored, error = None, False, 0, None, None
    try:
        world = client.generate_opendrive_world(road.read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
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
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        lanes = {}
        for name, authored_y in (('right', -1.75), ('left', 1.75)):
            waypoint = mapping.get_waypoint(carla.Location(x=40, y=-authored_y, z=1),
                                            project_to_road=False, lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.road_id != 1:
                raise RuntimeError('Native two-way lane readback absent: '+name)
            lanes[name] = waypoint.lane_id
        if lanes['right'] == lanes['left']:
            raise RuntimeError('Native opposing lanes collapse')
        library = world.get_blueprint_library()
        blueprint = library.find('vehicle.tesla.model3')
        for role, row_key, yaw in (('ego', 'ego_center_xy_m', 0),
                                   ('overtaken', 'overtaken_center_xy_m', 0),
                                   ('oncoming', 'oncoming_center_xy_m', 180)):
            x, y = requests[0][row_key]
            bp = library.find('vehicle.tesla.model3') if role == 'ego' else library.find('vehicle.audi.tt')
            bp.set_attribute('role_name', 'c102951_'+role)
            actor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=-y, z=2), carla.Rotation(yaw=yaw)))
            owned.append(actor)
        ego, overtaken, oncoming = owned
        for _ in range(40):
            world.tick()
        write_new(output/'native-map-readback.json', {
            'road_sha256': sha(road),
            'native_map_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'right_lane_id': lanes['right'], 'opposing_lane_id': lanes['left'],
            'ego_actor_id': ego.id, 'overtaken_actor_id': overtaken.id,
            'oncoming_actor_id': oncoming.id,
            'highway_status_reviewed': False,
            'driver_eye_visibility_reviewed': False})
        cameras = (('overview', 1920, 1080, 80, (70, -25, 35)),
                   ('forward', 1280, 720, 90, (0, 0, 0)))
        for name, width, height, fov, location in cameras:
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', fov), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            transform = (carla.Transform(carla.Location(x=location[0], y=location[1], z=location[2]),
                                         carla.Rotation(yaw=0, pitch=-25)) if name == 'overview'
                         else carla.Transform(carla.Location(x=1.0, y=0, z=1.4)))
            sensor = world.spawn_actor(bp, transform, attach_to=None if name == 'overview' else ego)
            owned.append(sensor)
            camera_queues[name] = queue.Queue()
            logs[name] = (output/(name+'.encoder.log')).open('x')
            video[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output/(name+'.mkv'))], stdin=subprocess.PIPE, stderr=logs[name])
            sensor.listen(camera_queues[name].put)
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False, required_observations=[])
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-actors.jsonl').open('x') as observed, \
             (output/'video_frames.jsonl').open('x') as frame_map:
            for i, request in enumerate(requests):
                lookahead = requests[min(479, i+15)]
                target = lookahead['ego_center_xy_m']
                command = steering(carla, ego, (target[0], -target[1]),
                                   request['ego_speed_mps'])
                ego.apply_control(command)
                overtaken.set_target_velocity(carla.Vector3D(x=8, y=0, z=0))
                oncoming.set_target_velocity(carla.Vector3D(x=-12, y=0, z=0))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds-start
                actors = {'frame': i, 'native_frame': frame, 'time_s': time_s,
                          'source_kind': 'original_native',
                          'ego': pose_record(ego), 'overtaken': pose_record(overtaken),
                          'oncoming': pose_record(oncoming),
                          'driver_eye_sightline_status': 'pending_source_review',
                          'safe_distance_judgment': None,
                          'interference_judgment': None,
                          'legal_verdict': None}
                capture.capture(frame, time_s, extra={'c102951_passing': actors})
                observed.write(json.dumps(actors, allow_nan=False)+'\n')
                for name, width, height, _, _ in cameras:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Camera/Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    video[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame': i, 'native_frame': frame,
                                            'time_s': time_s}, allow_nan=False)+'\n')
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, process in video.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: '+name)
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
        write_new(output/'native-capture-report.json', {
            'case_id': AID+'__'+str(distance), 'candidate_id': candidate,
            'bundle_config_sha256': sha(bundle/'config.json'),
            'requested_frames': 480, 'observed_frames': frames,
            'restoration': restored, 'error': error, 'accepted': False,
            'highway_status_reviewed': False,
            'driver_eye_visibility_reviewed': False,
            'legal_outcome_claimed': False})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--distance', type=int, choices=(70, 120, 170), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.bundle, args.distance, args.candidate)))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Native capture requires --output-dir, --host and --port')
        execute(args.bundle, args.distance, args.candidate, args.output_dir, args.host, args.port)
