"""Prospective Native route choice, with source capture and no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive

ASSIGNMENT = 'training__C230259__NRS-484B-627-1c__motor_vehicle_driver'
RATE = 20
FRAMES = 900
CAMERAS = (
    ('overview', 1920, 1080, 15, -36, 28, -45),
    ('approach', 1280, 720, -20, -12, 12, -25),
    ('reference_corner', 1280, 720, 30, -30, 14, -35),
    ('driver_reference', 1280, 720, 145, -18, 20, -40),
)


def check(alternate_possible=True):
    geometry = geometry_check(alternate_possible)
    if FRAMES / RATE != 45 or len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('exact 45-second four-camera capture changed')
    return {'passed': True, 'geometry': geometry, 'frames': FRAMES, 'rate_hz': RATE,
            'cameras': [c[0] for c in CAMERAS], 'physical_acceptance_claimed': False}


def route_points(mapping, road_ids):
    points = []
    for road_id in road_ids:
        length = {1: 100, 2: 150, 3: 70 + 40 * math.pi, 4: 100}[road_id]
        for s in range(0, int(length), 2):
            wp = mapping.get_waypoint_xodr(road_id, -1, float(s))
            if wp is None or wp.road_id != road_id or wp.lane_id != -1:
                raise RuntimeError('Native route waypoint missing: road ' + str(road_id))
            points.append(wp.transform.location)
    return points


def survey(mapping, alternate_possible):
    main = route_points(mapping, [1, 2, 4])
    alternative = route_points(mapping, [1, 3, 4]) if alternate_possible else None
    start = mapping.get_waypoint_xodr(1, -1, 80.0)
    if start is None:
        raise RuntimeError('Native subject start missing')
    return {'main_points': main, 'alternate_points': alternative,
            'subject_start': start.transform,
            'controlled_access_designation_independently_verified': False,
            'alternate_route_usability_physically_verified': False}


def _follow(actor, points, speed_mps, carla, lookahead_points=4):
    pose = actor.get_transform()
    xy = pose.location
    nearest = min(range(len(points)), key=lambda j:
                  (points[j].x - xy.x) ** 2 + (points[j].y - xy.y) ** 2)
    if not 2 <= lookahead_points <= 5:
        raise ValueError('unreviewed route lookahead')
    target = points[min(nearest + lookahead_points, len(points) - 1)]
    heading = math.radians(pose.rotation.yaw)
    desired = math.atan2(target.y - xy.y, target.x - xy.x)
    error = (desired - heading + math.pi) % (2 * math.pi) - math.pi
    actual = actor.get_velocity().length()
    steer = max(-0.8, min(0.8, 1.5 * error))
    throttle = max(0.0, min(0.55, 0.25 + 0.15 * (speed_mps - actual)))
    brake = max(0.0, min(0.5, 0.2 * (actual - speed_mps)))
    actor.apply_control(carla.VehicleControl(throttle=throttle, steer=steer, brake=brake))
    return {'target_xy_m': [target.x, target.y], 'speed_request_mps': speed_mps,
            'steer_command': steer, 'throttle_command': throttle, 'brake_command': brake,
            'nearest_route_point_index': nearest}


def execute(output_dir, case_id, alternate_possible, take_alternate, host, port,
            lookahead_points=4):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import snapshot, restore

    check(alternate_possible)
    if case_id not in {ASSIGNMENT + '__' + suffix for suffix in
                       ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')}:
        raise ValueError('unknown exact case')
    if take_alternate and not alternate_possible:
        raise ValueError('cannot request a disconnected alternate route')
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('choose fresh original attempt directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('requires exclusive idle asynchronous Native world')
    owned, encoders, cameras, encoder_codes = [], {}, {}, {}
    capture = None
    changed = False
    completed = False
    try:
        source_map = open_drive(alternate_possible)
        world = client.generate_opendrive_world(source_map,
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
        mapping = world.get_map()
        surveyed = survey(mapping, alternate_possible)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'road.xodr').write_text(mapping.to_opendrive())
        road_bytes = (output / 'road.xodr').read_bytes()
        route_context = {'assignment_id': ASSIGNMENT, 'case_id': case_id,
            'source_kind': 'native_saved_sample', 'road_xodr_sha256':
                hashlib.sha256(road_bytes).hexdigest(),
            'route_graph': {'start_road_id': 1, 'main_road_id': 2,
                            'alternate_road_id': 3 if alternate_possible else None,
                            'destination_road_id': 4},
            'controlled_access_designation_source': None,
            'controlled_access_designation_independently_verified': False,
            'alternate_route_usability_physically_verified': False,
            'planned_take_alternate': take_alternate,
            'planned_alternate_possible': alternate_possible,
            'legal_impediment_determined': False, 'legal_verdict': None}
        (output / 'route-context.json').write_text(json.dumps(route_context, indent=2) + '\n')
        blueprints = world.get_blueprint_library()
        subject_bp = blueprints.find('vehicle.tesla.model3')
        subject_bp.set_attribute('role_name', 'c230259_route_subject')
        follower_bp = blueprints.find('vehicle.audi.tt')
        follower_bp.set_attribute('role_name', 'c230259_immediately_following')
        lead_pose = surveyed['subject_start']
        lead_pose.location.z += 1
        ego = world.spawn_actor(subject_bp, lead_pose)
        owned.append(ego)
        for gap in (15.0, 31.0):
            following_wp = mapping.get_waypoint_xodr(1, -1, 80 - gap)
            if following_wp is None:
                raise RuntimeError('following vehicle waypoint missing')
            pose = following_wp.transform
            pose.location.z += 1
            vehicle = world.spawn_actor(follower_bp, pose)
            owned.append(vehicle)
        followers = owned[1:3]
        for name, width, height, x, y, z, pitch in CAMERAS:
            camera_bp = blueprints.find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', str(width))
            camera_bp.set_attribute('image_size_y', str(height))
            camera_bp.set_attribute('fov', '85')
            camera_bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            images = queue.Queue()
            camera.listen(images.put)
            cameras[name] = images
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', str(RATE), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        capture = PipelineCapture(client, ego, output, case_id, required_observations=[])
        route = surveyed['alternate_points'] if take_alternate else surveyed['main_points']
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'route-trace.jsonl').open('x') as trace:
            first_time = None
            for index in range(FRAMES):
                ego_command = _follow(ego, route, 6.0, carla, lookahead_points)
                follower_commands = []
                for follower in followers:
                    gap = ego.get_transform().location.distance(follower.get_transform().location)
                    desired = 6.0 if gap < 25 else 9.0
                    follower_commands.append(_follow(follower, surveyed['main_points'],
                                                     desired, carla, lookahead_points))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if first_time is None:
                    first_time = snap.timestamp.elapsed_seconds
                relative = snap.timestamp.elapsed_seconds - first_time
                camera_frames = {}
                for name, images in cameras.items():
                    image = images.get(timeout=30)
                    while image.frame < native_frame:
                        image = images.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('original camera frame join failed: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, relative, camera_native_frames=camera_frames)
                ego_wp = mapping.get_waypoint(ego.get_transform().location,
                    project_to_road=True, lane_type=carla.LaneType.Driving)
                following = []
                for vehicle, command in zip(followers, follower_commands):
                    position = vehicle.get_transform().location
                    waypoint = mapping.get_waypoint(position, project_to_road=True,
                                                    lane_type=carla.LaneType.Driving)
                    following.append({'actor_id': str(vehicle.id),
                        'xy_m': [position.x, position.y],
                        'speed_mps': vehicle.get_velocity().length(),
                        'road_id': waypoint.road_id if waypoint else None,
                        'lane_id': waypoint.lane_id if waypoint else None,
                        'controller': command, 'unimpeded_request_mps': 9.0})
                ego_pos = ego.get_transform().location
                sample = {'video_frame': index, 'native_frame': native_frame,
                    'time_s': relative, 'native_elapsed_seconds': snap.timestamp.elapsed_seconds,
                    'camera_native_frames': camera_frames,
                    'ego': {'actor_id': str(ego.id), 'xy_m': [ego_pos.x, ego_pos.y],
                        'speed_mps': ego.get_velocity().length(),
                        'road_id': ego_wp.road_id if ego_wp else None,
                        'lane_id': ego_wp.lane_id if ego_wp else None,
                        'controller': ego_command}, 'following': following}
                capture.capture(native_frame, relative, extra={'c230259_route': sample})
                trace.write(json.dumps(sample, allow_nan=False) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            if encoder_codes[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('camera encoder failed: ' + name + error.decode()[-200:])
        capture.close(confirmed=True)
        capture = None
        completed = True
        return {'frames': FRAMES, 'case_id': case_id, 'source_saved': True,
                'physical_acceptance_claimed': False}
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
            if completed and len(encoder_codes) == 4:
                seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                    encoder_exit_codes=encoder_codes, context={'case_id': case_id})
                record_native_exit(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--case-id')
    parser.add_argument('--alternate-possible', action='store_true')
    parser.add_argument('--take-alternate', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config_path = Path(__file__).with_name('config.json')
    config = json.loads(config_path.read_text()) if config_path.is_file() else None
    if args.check:
        print(json.dumps(check(config['alternate_possible'] if config else args.alternate_possible)))
    else:
        if not args.output_dir or config is None:
            raise SystemExit('--output-dir and materialized config.json required for original Native attempt')
        print(json.dumps(execute(args.output_dir, config['case_id'],
            config['alternate_possible'], config['take_alternate'], args.host, args.port,
            config['lookahead_points'])))
