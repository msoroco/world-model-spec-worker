"""Native sidewalk-stop capture; requests are not physical or legal findings."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from draft_runner import ASSIGNMENT, capture_row
from sidewalk_occupancy import measure_frame

FRAMES = 600
RATE = 20
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def request(frame, case_id):
    if not 0 <= frame < FRAMES or not case_id.endswith(('__traffic_conflict_absent', '__traffic_conflict_present')):
        raise ValueError('exact traffic-conflict case required')
    return {'target_speed_mps': 0.0 if 160 <= frame < 500 else 4.0,
            'target_lateral_m': -5.0,
            'requested_sidewalk_occupancy': True}


def check(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-450-1a', 'C229977', 'motor_vehicle_driver'):
        raise ValueError('frozen identity differs')
    case_id = config.get('case_id')
    if case_id not in (ASSIGNMENT + '__traffic_conflict_absent',
                       ASSIGNMENT + '__traffic_conflict_present'):
        raise ValueError('exact selected case required')
    if config.get('rate_hz') != RATE or config.get('duration_s') != 30:
        raise ValueError('20 Hz and 30 seconds required')
    if tuple(item.get('name') for item in config.get('cameras', [])) != CAMERAS:
        raise ValueError('four original source cameras required')
    engineering = config.get('engineering', {})
    if engineering.get('lateral_gain') not in (0.18, 0.24) or \
            engineering.get('brake_start_x_m') not in (27, 31):
        raise ValueError('declared engineering profile required')
    road = ET.fromstring((Path(__file__).resolve().parent / 'authored-road.xodr').read_text())
    sidewalk = road.find(".//lane[@id='-2']")
    if sidewalk is None or sidewalk.get('type') != 'sidewalk':
        raise ValueError('authored sidewalk lane missing')
    return {'case_id': case_id, 'frames': FRAMES, 'rate_hz': RATE,
            'native_capture_implemented': True,
            'physical_acceptance_claimed': False}


def footprint(vertices):
    """Convex hull of all eight source bbox vertices in the ground plane."""
    points = sorted(set((float(v[0]), float(v[1])) for v in vertices))
    if len(points) < 3:
        raise ValueError('native vehicle body has no footprint')
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1] + upper[:-1]]


def survey(carla, world):
    mapping = world.get_map()
    result = []
    for x in (5, 25, 45, 65, 85):
        point = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=0),
                                     project_to_road=True,
                                     lane_type=carla.LaneType.Driving)
        if point is None or point.road_id != 1 or point.lane_id != -1:
            raise RuntimeError('original driving-lane survey failed')
        result.append({'requested_x_m': x, 'road_id': point.road_id,
                       'lane_id': point.lane_id,
                       'native_xyz_m': [point.transform.location.x,
                                        point.transform.location.y,
                                        point.transform.location.z]})
    return result


def polygon_from_lane(carla, world):
    """Map geometry packet; legal sidewalk status still needs independent review."""
    mapping = world.get_map()
    rows = []
    for x in (0, 100):
        point = mapping.get_waypoint(carla.Location(x=x, y=-5.0, z=0),
                                     project_to_road=True,
                                     lane_type=carla.LaneType.Sidewalk)
        if point is None or point.road_id != 1 or point.lane_id != -2:
            raise RuntimeError('original sidewalk-lane survey failed')
        rows.append([point.transform.location.x, point.transform.location.y,
                     point.transform.location.z, point.lane_width])
    ys = [p[1] for p in rows]
    widths = [p[3] for p in rows]
    lower = min(y - width / 2 for y, width in zip(ys, widths))
    upper = max(y + width / 2 for y, width in zip(ys, widths))
    return {'map_acquisition': 'native_get_map_to_opendrive_and_waypoint_survey',
            'native_sidewalk_lane_survey': rows,
            'sidewalk_polygon_m': [[0, lower], [100, lower],
                                   [100, upper], [0, upper]],
            'highway_boundary_source': None,
            'property_boundary_source': None,
            'intended_pedestrian_use_source': None,
            'legal_sidewalk_status': None}


def control(carla, actor, frame, case_id, engineering):
    target = request(frame, case_id)
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    x, y = transform.location.x, transform.location.y
    # Engineering request: approach from the road, steer laterally toward the
    # case target, brake at the fixed stop zone. Native motion is measured later.
    lateral_error = target['target_lateral_m'] - y
    steer = max(-0.45, min(0.45, -engineering['lateral_gain'] * lateral_error))
    stop_zone = engineering['brake_start_x_m'] <= x <= 55 and 130 <= frame < 500
    brake = 1.0 if stop_zone else 0.0
    throttle = 0.0 if brake else min(0.40, max(0.0, 0.23 * (4.0 - speed)))
    actor.apply_control(carla.VehicleControl(throttle=throttle, brake=brake,
                                             steer=steer))
    return {'requested_speed_mps': target['target_speed_mps'],
            'requested_lateral_m': target['target_lateral_m'],
            'requested_throttle': throttle, 'requested_brake': brake,
            'requested_steer': steer,
            'requested_sidewalk_occupancy': target['requested_sidewalk_occupancy']}


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError('fresh empty output directory required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('exclusive idle Native world required')
    owned, encoders, camera_queues = [], {}, {}
    capture = None
    exits = {}
    changed = False
    completed = False
    try:
        world = client.generate_opendrive_world((Path(__file__).resolve().parent / 'authored-road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=25, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        survey_rows = survey(carla, world)
        original_road = world.get_map().to_opendrive()
        (output / 'native-road.xodr').write_text(original_road)
        (output / 'road.xodr').write_text(original_road)
        map_packet = polygon_from_lane(carla, world)
        map_packet['sidewalk_map_context'] = {
            'source': 'original Native map survey',
            'legal_status_independently_verified': False}
        (output / 'map-packet.json').write_text(json.dumps(map_packet, sort_keys=True) + '\n')
        (output / 'road-survey.json').write_text(json.dumps(
            {'source_kind': 'original_native', 'lane_survey': survey_rows,
             'legal_highway_boundary_verified': False}, sort_keys=True) + '\n')
        (output / 'authority-context.json').write_text(json.dumps({
            'source_kind': 'original_native_request',
            'traffic_conflict_requested': config['case_id'].endswith('_present'),
            'traffic_conflict_source': 'traffic-trace.jsonl',
            'traffic_conflict_independently_verified': False,
            'other_law_authority': None,
            'officer_direction': None,
            'official_device_direction': None,
            'exception_independently_verified': False,
            'exception_authority_context': {
                'source': 'original Native request and authority review pending',
                'independently_verified': False}}, sort_keys=True) + '\n')
        library = world.get_blueprint_library()
        vehicle_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        vehicle_bp.set_attribute('role_name', 'c229977_subject')
        vehicle = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=5, y=-1.75, z=1.5), carla.Rotation(yaw=0)))
        owned.append(vehicle)
        traffic = None
        if config['case_id'].endswith('_present'):
            traffic_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
            traffic_bp.set_attribute('role_name', 'c229977_other_traffic_request')
            traffic = world.spawn_actor(traffic_bp, carla.Transform(
                carla.Location(x=38, y=-1.75, z=1.5), carla.Rotation(yaw=0)))
            owned.append(traffic)
        mounts = {'overview': (32, 14, 28, -35),
                  'approach': (8, 5, 12, -18),
                  'reference_corner': (40, -10, 10, -20),
                  'driver_reference': (42, 8, 7, -12)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(item for item in config['cameras'] if item['name'] == name)
            blueprint = library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(spec['width']))
            blueprint.set_attribute('image_size_y', str(spec['height']))
            blueprint.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        capture = PipelineCapture(client, vehicle, output, config['case_id'],
                                  required_observations=[])
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'vehicle-trace.jsonl').open('x') as trace, \
                (output / 'camera-frames.jsonl').open('x') as camera_rows, \
                (output / 'traffic-trace.jsonl').open('x') as traffic_rows:
            initial_time = None
            for index in range(FRAMES):
                if traffic is not None:
                    traffic.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0))
                requested = control(carla, vehicle, index, config['case_id'],
                                    config['engineering'])
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                images = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('camera/native frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    images[name] = image.frame
                    camera_rows.write(json.dumps({'frame': index, 'camera': name,
                        'native_frame': native_frame,
                        'rgb_sha256': hashlib.sha256(image.raw_data).hexdigest()}) + '\n')
                frame_map.append(native_frame, time_s, camera_native_frames=images)
                row = capture_row(index, native_frame, time_s, vehicle)
                row['vehicle_footprint_m'] = footprint(row['body_vertices_m'])
                row['sidewalk_overlap_area_m2'] = measure_frame(
                    row['vehicle_footprint_m'], map_packet['sidewalk_polygon_m'])[
                        'sidewalk_overlap_area_m2']
                row['value'] = {'vehicle_body_pose': row['body_vertices_m'],
                                'vehicle_speed': row['speed_mps'],
                                'sidewalk_overlap': row['sidewalk_overlap_area_m2']}
                row.update(requested)
                trace.write(json.dumps(row, sort_keys=True) + '\n')
                traffic_row = capture_row(index, native_frame, time_s, traffic) if traffic is not None else {
                    'frame': index, 'native_frame': native_frame, 'time_s': time_s,
                    'traffic_actor_present': False}
                traffic_rows.write(json.dumps(traffic_row, sort_keys=True) + '\n')
                capture.capture(native_frame, time_s, extra={'sidewalk_stop': {
                    'vehicle_id': vehicle.id, 'camera_native_frames': images,
                    'requested_sidewalk_occupancy': requested['requested_sidewalk_occupancy']}})
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            exits[name] = process.wait(timeout=180)
            if exits[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('camera encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        capture.close(confirmed=True)
        capture = None
        completed = True
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'physical_acceptance_claimed': False,
                'legal_verdict_claimed': False}
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
            if completed:
                seal_capture(output, frames=FRAMES, restoration=restored,
                             errors=[], encoder_exit_codes=exits,
                             context={'case_id': config['case_id']})
                record_native_exit(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required')
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
