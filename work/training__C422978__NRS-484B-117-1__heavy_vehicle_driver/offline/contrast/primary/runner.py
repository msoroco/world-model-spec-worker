"""Exact heavy-vehicle Native capture. --check needs no CARLA installation."""
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

AID = 'training__C422978__NRS-484B-117-1__heavy_vehicle_driver'
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
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
BLUEPRINT = 'vehicle.carlamotors.carlacola'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle, case, candidate):
    bundle = Path(bundle)
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown exact heavy-vehicle case or candidate')
    canonical = bundle.resolve() == (CASE/'native'/'drafts'/case/candidate).resolve()
    config = json.loads((bundle/'config.json').read_text())
    expected = {'case_id': AID+'__'+case, 'case_suffix': case,
                'candidate_id': candidate, 'cell_id': 'C422978',
                'law_id': 'NRS-484B-117-1', 'actor': 'heavy_vehicle_driver',
                'rate_hz': 20, 'duration_s': 24,
                'status': 'unselected_native_request'}
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError('Exact heavy-vehicle configuration differs')
    road = (CASE/'native'/'road.xodr') if canonical else bundle/'road.xodr'
    assignment = (ROOT/'inputs'/AID/'assignment.json') if canonical else bundle/'assignment-source.json'
    plan = (CASE/'case-plan.json') if canonical else bundle/'case-plan.json'
    sources = ((road, 'road_sha256'),
               (bundle/'requested-tracks.jsonl', 'tracks_sha256'),
               (assignment, 'assignment_sha256'),
               (plan, 'case_plan_sha256'))
    if any(sha(path) != config[key] for path, key in sources):
        raise ValueError('Exact frozen or authored source hash differs')
    lanes = {int(lane.attrib['id']): lane.attrib['type'] for lane in
             ET.parse(road).findall('.//lane')}
    if lanes.get(1) != 'driving' or lanes.get(-1) != 'driving' or lanes.get(-2) != 'sidewalk':
        raise ValueError('Authored two-way road or sidewalk lane absent')
    rows = [json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows) != 480:
        raise ValueError('Heavy-vehicle request frame count differs')
    for index, row in enumerate(rows):
        if (row['frame'] != index or abs(row['time_s']-index/20) > 1e-6 or
                row['subject_blueprint_request'] != BLUEPRINT or
                row['source_kind'] != 'authored_native_request' or
                row['requested_speed_mps'] != 4 or
                row['camera_fov_deg'] != config['policy']['camera_fov_deg'] or
                row['driveway_or_alley_requested'] is not False):
            raise ValueError('Heavy-vehicle request frame or controls differ')
    return {'passed': True, 'case_id': expected['case_id'],
            'candidate_id': candidate, 'requested_frames': len(rows),
            'carla_imported': False, 'original_native_observed': False,
            'physical_or_legal_outcome_claimed': False}


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def body_xy(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
    if len(points) != 4:
        raise RuntimeError('Native heavy-vehicle body lacks four XY vertices')
    return [list(point) for point in points]


def camera_pose(carla, name):
    xyz = {'overview': (55, -20, 35), 'front': (30, -12, 11),
           'sidewalk': (55, -14, 12), 'rear': (110, -12, 14)}[name]
    x, y, z = xyz
    target = (60, 5, 1)
    yaw = math.degrees(math.atan2(target[1]-y, target[0]-x))
    pitch = math.degrees(math.atan2(target[2]-z, math.hypot(target[0]-x, target[1]-y)))
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def control(carla, actor, target, wheelbase, max_steer):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    dx, dy = target[0]-pose.location.x, target[1]-pose.location.y
    alpha = math.atan2(dy, dx)-math.radians(pose.rotation.yaw)
    alpha = math.atan2(math.sin(alpha), math.cos(alpha))
    angle = math.atan2(2*wheelbase*math.sin(alpha), max(.1, math.hypot(dx, dy)))
    steer = max(-.8, min(.8, angle/math.radians(max_steer)))
    throttle = max(0, min(1, .15+.4*(4-speed)))
    brake = max(0, min(1, .4*(speed-4)))
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer), {
        'target_native_xy_m': list(target), 'observed_speed_mps': speed,
        'throttle': throttle, 'brake': brake, 'steer': steer}


def execute(bundle, output, case, candidate, host, port):
    """Record an original attempt into a fresh directory; never mark it accepted."""
    check(bundle, case, candidate)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Native output must be a fresh directory')
    output.mkdir(parents=True)
    repo = ROOT
    sys.path.insert(0, str(repo/'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0, str(repo/'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    config = json.loads((Path(bundle)/'config.json').read_text())
    requests = [json.loads(line) for line in (Path(bundle)/'requested-tracks.jsonl').read_text().splitlines()]
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(
            a.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for a in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned, encoders, logs, queues = [], {}, {}, {}
    capture, changed, frames, restored, error = None, False, 0, None, None
    cameras = [('overview', 1920, 1080, 80), ('front', 1280, 720, 80),
               ('sidewalk', 1280, 720, config['policy']['camera_fov_deg']),
               ('rear', 1280, 720, 85)]
    try:
        road = (CASE/'native'/'road.xodr') if Path(bundle).resolve() == (CASE/'native'/'drafts'/case/candidate).resolve() else Path(bundle)/'road.xodr'
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
        sidewalk = mapping.get_waypoint(carla.Location(x=50, y=5.5, z=.3),
            project_to_road=False, lane_type=carla.LaneType.Sidewalk)
        if sidewalk is None or sidewalk.road_id != 1 or sidewalk.lane_id != -2:
            raise RuntimeError('Native sidewalk readback differs')
        blueprint = world.get_blueprint_library().find(BLUEPRINT)
        blueprint.set_attribute('role_name', 'c422978_heavy_vehicle_subject')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=10, y=1.75, z=1), carla.Rotation(yaw=0)))
        owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(40):
            world.tick()
        wheels = ego.get_physics_control().wheels
        wheelbase = (max(w.position.x for w in wheels)-min(w.position.x for w in wheels))/100
        max_steer = max(w.max_steer_angle for w in wheels)
        if len(wheels) < 4 or wheelbase <= 0 or max_steer <= 0:
            raise RuntimeError('Native heavy-vehicle wheel geometry invalid')
        body = body_xy(ego)
        width = max(p[1] for p in body)-min(p[1] for p in body)
        if not 1.5 <= width <= 3.6:
            raise RuntimeError('Native heavy-vehicle width lacks 0.2 m sidewalk clearance per side')
        write_new(output/'native-map-readback.json', {
            'native_map_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'sidewalk_road_id': sidewalk.road_id, 'sidewalk_lane_id': sidewalk.lane_id,
            'subject_actor_id': ego.id, 'subject_blueprint': ego.type_id,
            'observed_body_width_m': width, 'sidewalk_clearance_each_side_m': (4-width)/2,
            'observed_wheelbase_m': wheelbase,
            'city_location_verified': False})
        for name, w, h, fov in cameras:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', w), ('image_size_y', h),
                               ('fov', fov), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, camera_pose(carla, name))
            owned.append(sensor)
            queues[name] = queue.Queue()
            logs[name] = (output/(name+'.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}',
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output/(name+'.mkv'))], stdin=subprocess.PIPE, stderr=logs[name])
            sensor.listen(queues[name].put)
        capture = PipelineCapture(client, ego, output, config['case_id'],
            visibility=False, required_observations=['rel.occupies', 'kin.velocity'])
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-observed.jsonl').open('x') as observed, \
             (output/'video_frames.jsonl').open('x') as mapping_file:
            for index in range(480):
                target = requests[min(479, index+15)]['requested_center_xy_m']
                command, command_record = control(carla, ego, (target[0], -target[1]),
                                                   wheelbase, max_steer)
                ego.apply_control(command)
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds-start
                pose, velocity = ego.get_transform(), ego.get_velocity()
                speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                lane = mapping.get_waypoint(pose.location, project_to_road=False,
                                            lane_type=carla.LaneType.Any)
                sample = {'frame': index, 'native_frame': frame, 'time_s': time_s,
                          'source_kind': 'original_native', 'vehicle_blueprint': ego.type_id,
                          'center_native_xy_m': [pose.location.x, pose.location.y],
                          'body_native_xy_m': body_xy(ego), 'speed_mps': speed,
                          'native_road_id': None if lane is None else lane.road_id,
                          'native_lane_id': None if lane is None else lane.lane_id,
                          'control_request': command_record}
                capture.capture(frame, time_s, extra={'c422978_heavy_vehicle': sample})
                observed.write(json.dumps(sample, allow_nan=False)+'\n')
                for name, w, h, _ in cameras:
                    image = queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera/Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        h, w, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                mapping_file.write(json.dumps({'video_frame': index,
                    'native_frame': frame, 'carla_frame': frame,
                    'time_s': time_s}, allow_nan=False)+'\n')
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
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, process in encoders.items():
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
            'case_id': AID+'__'+case, 'candidate_id': candidate,
            'bundle_config_sha256': sha(Path(bundle)/'config.json'),
            'requested_frames': 480, 'observed_frames': frames,
            'restoration': restored, 'error': error, 'accepted': False,
            'city_sidewalk_verified': False, 'legal_outcome_claimed': False})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.bundle, args.case, args.candidate)))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Native capture requires --output-dir, --host and --port')
        execute(args.bundle, args.output_dir, args.case, args.candidate,
                args.host, args.port)
