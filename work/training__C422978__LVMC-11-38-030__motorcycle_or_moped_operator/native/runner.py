"""Exact C422978 motorcycle capture; CPU check never starts CARLA."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
AID = 'training__C422978__LVMC-11-38-030__motorcycle_or_moped_operator'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(folder, case, candidate):
    folder = Path(folder)
    if case not in ('witness_1', 'witness_2') or candidate not in (
            'primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown exact case or candidate')
    config = json.loads((folder / 'config.json').read_text())
    if (config['case_id'] != AID + '__' + case or
            config['candidate_id'] != candidate or
            config['cell_id'] != 'C422978' or
            config['law_id'] != 'LVMC-11-38-030' or
            config['actor'] != 'motorcycle_or_moped_operator' or
            config['rate_hz'] != 20 or config['duration_s'] != 24):
        raise ValueError('Exact motorcycle case configuration differs')
    road = folder / 'authored-road.xodr'
    tracks = folder / 'requested-tracks.jsonl'
    if sha(road) != config['road_sha256'] or sha(tracks) != config['tracks_sha256']:
        raise ValueError('Authored road or motorcycle tracks differ')
    source = folder / 'assignment-source.json'
    if sha(source) != config['assignment_sha256']:
        raise ValueError('Frozen motorcycle assignment source differs')
    lanes = {int(lane.attrib['id']): lane.attrib['type'] for lane in
             ET.parse(road).findall('.//lane')}
    if lanes.get(1) != 'driving' or lanes.get(-1) != 'driving' or lanes.get(-2) != 'sidewalk':
        raise ValueError('Two-way road or sidewalk lane absent')
    rows = [json.loads(line) for line in tracks.read_text().splitlines()]
    if len(rows) != 480:
        raise ValueError('Motorcycle request frame count differs')
    for index, row in enumerate(rows):
        if (row['frame'] != index or abs(row['time_s'] - index/20) > 1e-4 or
                row['motorcycle_blueprint'] != 'vehicle.kawasaki.ninja' or
                row['requested_speed_mps'] != 4.0 or
                row['source_kind'] != 'authored_native_request'):
            raise ValueError('Motorcycle request frame/identity differs')
    overlap = [row['frame'] for row in rows if
               row['requested_center_xy_m'][1] - .4 < -3.5 and
               row['requested_center_xy_m'][1] + .4 > -5.5]
    if (bool(overlap) != (case == 'witness_2') or
            (overlap and len(overlap) < 390)):
        raise ValueError('Paired requested sidewalk occupancy differs')
    return {'passed': True, 'case_id': config['case_id'], 'candidate_id': candidate,
            'track_rows': len(rows), 'requested_sidewalk_overlap_frames': len(overlap),
            'carla_imported': False, 'original_native_observed': False,
            'physical_or_legal_outcome_claimed': False}


def _write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def _body_xy(actor):
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in
                     actor.bounding_box.get_world_vertices(actor.get_transform())})
    if len(points) != 4:
        raise RuntimeError('Native motorcycle body lacks four XY vertices')
    return [list(point) for point in points]


def _camera_pose(carla, name):
    locations = {
        'overview': (55, -22, 32),
        'front': (30, -12, 8),
        'sidewalk': (55, -12, 9),
        'rear': (105, -11, 11),
    }
    x, y, z = locations[name]
    target_x, target_y, target_z = 58, 4, 0
    yaw = math.degrees(math.atan2(target_y - y, target_x - x))
    pitch = math.degrees(math.atan2(target_z - z,
                                    math.hypot(target_x - x, target_y - y)))
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def _control(carla, actor, target, wheelbase_m, max_steer_deg):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    dx, dy = target[0] - pose.location.x, target[1] - pose.location.y
    alpha = math.atan2(dy, dx) - math.radians(pose.rotation.yaw)
    alpha = math.atan2(math.sin(alpha), math.cos(alpha))
    steer_radians = math.atan2(2 * wheelbase_m * math.sin(alpha),
                              max(.1, math.hypot(dx, dy)))
    steer = max(-.8, min(.8, steer_radians / math.radians(max_steer_deg)))
    throttle = max(0, min(1, .15 + .4 * (4 - speed)))
    brake = max(0, min(1, .4 * (speed - 4)))
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer), {
        'target_native_xy_m': list(target), 'observed_speed_mps': speed,
        'throttle': throttle, 'brake': brake, 'steer': steer}


def execute(folder, case, candidate, host, port):
    """Record an original attempt in a fresh exact bundle; acceptance is separate."""
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / 'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0, str(repo / 'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore

    folder = Path(folder).resolve()
    check(folder, case, candidate)
    config = json.loads((folder / 'config.json').read_text())
    requests = [json.loads(line) for line in
                (folder / 'requested-tracks.jsonl').read_text().splitlines()]
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned, encoders, logs, queues = [], {}, {}, {}
    capture = None
    changed, frames, restored, error = False, 0, None, None
    cameras = [('overview', 1920, 1080, 80),
               ('front', 1280, 720, 80),
               ('sidewalk', 1280, 720, config['policy']['camera_fov_deg']),
               ('rear', 1280, 720, 85)]
    try:
        road = (folder / 'authored-road.xodr').read_text()
        world = client.generate_opendrive_world(road, carla.OpendriveGenerationParameters(
            vertex_distance=.25, max_road_length=50, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
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
        native_xml = mapping.to_opendrive()
        native_map_sha = hashlib.sha256(native_xml.encode()).hexdigest()
        lane = mapping.get_waypoint(carla.Location(x=50, y=4.5, z=.3),
                                    project_to_road=False,
                                    lane_type=carla.LaneType.Sidewalk)
        if lane is None or lane.road_id != 1 or lane.lane_id != -2:
            raise RuntimeError('Native sidewalk lane readback differs')
        library = world.get_blueprint_library()
        blueprint = library.find('vehicle.kawasaki.ninja')
        blueprint.set_attribute('role_name', 'c422978_motorcycle_subject')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=10, y=1.75, z=.6), carla.Rotation(yaw=0)))
        owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(40): world.tick()
        wheels = ego.get_physics_control().wheels
        if len(wheels) != 2:
            raise RuntimeError('Native motorcycle two-wheel geometry absent')
        wheelbase = (max(w.position.x for w in wheels) -
                     min(w.position.x for w in wheels)) / 100
        max_steer = max(w.max_steer_angle for w in wheels)
        if wheelbase <= 0 or max_steer <= 0:
            raise RuntimeError('Native motorcycle steering geometry invalid')
        _write_new(folder / 'native-map-readback.json', {
            'native_map_sha256': native_map_sha, 'sidewalk_road_id': lane.road_id,
            'sidewalk_lane_id': lane.lane_id, 'motorcycle_actor_id': ego.id,
            'motorcycle_blueprint': ego.type_id, 'city_location_verified': False})
        for name, width, height, fov in cameras:
            camera_bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', fov), ('sensor_tick', 0)):
                camera_bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(camera_bp, _camera_pose(carla, name))
            owned.append(sensor)
            queues[name] = queue.Queue()
            logs[name] = (folder / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(folder / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=logs[name])
            sensor.listen(queues[name].put)
        capture = PipelineCapture(client, ego, folder, config['case_id'],
                                  visibility=False,
                                  required_observations=['rel.occupies', 'kin.velocity'])
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (folder / 'native-observed.jsonl').open('x') as observed_file, \
             (folder / 'video_frames.jsonl').open('x') as mapping_file:
            for index in range(480):
                target = requests[min(479, index + 15)]['requested_center_xy_m']
                target_native = (target[0], -target[1])
                command, control = _control(carla, ego, target_native,
                                            wheelbase, max_steer)
                ego.apply_control(command)
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                body = _body_xy(ego)
                native_lane = mapping.get_waypoint(pose.location,
                    project_to_road=False, lane_type=carla.LaneType.Any)
                sample = {'frame': index, 'native_frame': frame, 'time_s': time_s,
                          'source_kind': 'original_native',
                          'motorcycle_blueprint': ego.type_id,
                          'center_native_xy_m': [pose.location.x, pose.location.y],
                          'body_native_xy_m': body, 'speed_mps': speed,
                          'native_road_id': None if native_lane is None else native_lane.road_id,
                          'native_lane_id': None if native_lane is None else native_lane.lane_id,
                          'control_request': control}
                capture.capture(frame, time_s, extra={'c422978_motorcycle': sample})
                observed_file.write(json.dumps(sample, allow_nan=False) + '\n')
                for name, width, height, _ in cameras:
                    image = queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera/Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                mapping_file.write(json.dumps({'video_frame': index,
                    'native_frame': frame, 'carla_frame': frame,
                    'time_s': time_s}, allow_nan=False) + '\n')
                frames += 1
        if frames != 480:
            raise RuntimeError('Original Native frame count incomplete')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc: error = error or {'capture_close_error': str(exc)}
        for name, process in encoders.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: ' + name)
            except BaseException as exc: error = error or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening: actor.stop()
                actor.destroy()
            except BaseException as exc: error = error or {'cleanup_error': str(exc)}
        if changed:
            try: restored = restore(client, saved)
            except BaseException as exc: error = error or {'restore_error': str(exc)}
        _write_new(folder / 'native-capture-report.json', {
            'case_id': AID + '__' + case, 'candidate_id': candidate,
            'frames': frames, 'expected_frames': 480,
            'restoration': restored, 'error': error, 'accepted': False,
            'city_sidewalk_verified': False, 'legal_outcome_claimed': False})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', '--output-dir', type=Path, default=HERE)
    parser.add_argument('--case')
    parser.add_argument('--candidate')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads((args.folder / 'config.json').read_text())
    case, candidate = args.case or config['case_suffix'], args.candidate or config['candidate_id']
    if args.check:
        print(json.dumps(check(args.folder, case, candidate)))
    else:
        if not args.host or not args.port:
            parser.error('Native capture requires --host and --port')
        execute(args.folder, case, candidate, args.host, args.port)
