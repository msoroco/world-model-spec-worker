"""Original Native two-vehicle curbside capture for NRS 484B.450(1)(l)."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from controller import TARGET_X_M, command, check as controller_check
from geometry import EGO_LATERAL, CURBSIDE_CENTER, check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check(config):
    geometry = geometry_check()
    controller_check()
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C229398', 'NRS-484B-450-1l', 'motor_vehicle_driver'):
        raise ValueError('Exact law/cell/actor identity changed')
    if config['case_id'].rsplit('__', 1)[-1] not in TARGET_X_M:
        raise ValueError('Unknown exact selected case')
    if config['rate_hz'] != RATE or config['duration_s'] != 30:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('Four original source cameras required')
    return {'geometry': geometry, 'frames': FRAMES, 'camera_names': CAMERAS,
            'original_native_executed': False, 'statutory_activity_or_exception_decided': False}


def survey(carla, mapping):
    observations = []
    for x in (-80.0, 0.0, 12.0, 80.0):
        for name, y, lane_type, expected in (
                ('travel', EGO_LATERAL, carla.LaneType.Driving, -1),
                ('parking', CURBSIDE_CENTER[1], carla.LaneType.Parking, -2)):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=1.4),
                                      project_to_road=True, lane_type=lane_type)
            if (wp is None or wp.road_id != 1 or wp.lane_id != expected or
                    abs(wp.transform.location.x - x) > 1.0 or
                    abs(wp.transform.location.y - y) > 0.8):
                raise RuntimeError('Original Native road/curb lane readback differs: ' + name)
            observations.append({'x_m': x, 'lane': name, 'road_id': wp.road_id,
                                 'lane_id': wp.lane_id, 'lane_width_m': wp.lane_width,
                                 'native_xyz_m': [wp.transform.location.x,
                                                  wp.transform.location.y,
                                                  wp.transform.location.z]})
    parking = [row for row in observations if row['lane'] == 'parking']
    curb = [[row['native_xyz_m'][0], row['native_xyz_m'][1] - row['lane_width_m'] / 2]
            for row in (parking[0], parking[-1])]
    if abs(curb[0][1] - curb[1][1]) > .3 or abs(curb[0][1] + 6.5) > .8:
        raise RuntimeError('Native curbside boundary differs from authored curb')
    return observations, curb


def footprint(actor):
    pose = actor.get_transform()
    extent = actor.bounding_box.extent
    theta = math.radians(pose.rotation.yaw)
    c, s = math.cos(theta), math.sin(theta)
    return [[pose.location.x + c * dx - s * dy,
             pose.location.y + s * dx + c * dy]
            for dx, dy in ((-extent.x, -extent.y), (-extent.x, extent.y),
                           (extent.x, extent.y), (extent.x, -extent.y))]


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'body-footprints.jsonl').exists():
        raise ValueError('Fresh materialized attempt required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned, encoders, camera_queues = [], {}, {}
    capture = None
    changed = complete = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
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
        readback, curb = survey(carla, world.get_map())
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'map-geometry.json').write_text(json.dumps({
            'source_kind': 'surveyed_map_geometry', 'cell_id': 'C229398',
            'curb_start_xy_m': curb[0], 'curb_end_xy_m': curb[1],
            'road_interior_normal_sign': 1, 'native_lane_survey': readback,
            'highway_dedication_verified': False, 'curb_authority_review_required': True},
            indent=2) + '\n')
        library = world.get_blueprint_library()
        bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        bp.set_attribute('role_name', 'c229398_subject')
        subject = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=-80, y=EGO_LATERAL, z=2.0), carla.Rotation(yaw=0)))
        owned.append(subject)
        parked_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        parked_bp.set_attribute('role_name', 'c229398_curbside')
        curbside = world.spawn_actor(parked_bp, carla.Transform(
            carla.Location(x=CURBSIDE_CENTER[0], y=CURBSIDE_CENTER[1], z=2.0),
            carla.Rotation(yaw=0)))
        owned.append(curbside)
        curbside.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
        capture = PipelineCapture(client, subject, output, config['case_id'],
                                  visibility=False,
                                  required_observations=config.get('required_atoms', []))
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'subject_actor_id': subject.id, 'curbside_actor_id': curbside.id,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        mounts = {'overview': (-8, -24, 24, -35), 'approach': (-24, -10, 9, -15),
                  'reference_corner': (-5, 9, 10, -20),
                  'driver_reference': (-35, 8, 10, -20)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            cbp = library.find('sensor.camera.rgb')
            cbp.set_attribute('image_size_x', str(spec['width']))
            cbp.set_attribute('image_size_y', str(spec['height']))
            cbp.set_attribute('sensor_tick', str(1 / RATE))
            cbp.set_attribute('fov', str(spec['fov_deg']))
            camera = world.spawn_actor(cbp, carla.Transform(
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
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'vehicle-poses.jsonl').open('x') as poses, \
                (output / 'body-footprints.jsonl').open('x') as bodies, \
                (output / 'trace.jsonl').open('x') as trace:
            initial_time = None
            for index in range(FRAMES):
                pose, vv = subject.get_transform(), subject.get_velocity()
                speed = math.sqrt(vv.x * vv.x + vv.y * vv.y + vv.z * vv.z)
                request = command(config['case_id'].rsplit('__', 1)[-1], index,
                                  pose.location.x, speed)
                subject.apply_control(carla.VehicleControl(
                    throttle=request['throttle'], brake=request['brake'],
                    steer=request['steer']))
                curbside.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                capture.capture(native_frame, time_s)
                camera_frames = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s,
                                 camera_native_frames=camera_frames)
                pose, vv = subject.get_transform(), subject.get_velocity()
                curb_pose = curbside.get_transform()
                speed = math.sqrt(vv.x * vv.x + vv.y * vv.y + vv.z * vv.z)
                trace.write(json.dumps({'frame': native_frame, 'time_s': time_s,
                    'position': {'x': pose.location.x, 'y': pose.location.y,
                                 'z': pose.location.z},
                    'position_m': [pose.location.x, pose.location.y, pose.location.z],
                    'heading_deg': pose.rotation.yaw, 'speed_mps': speed,
                    'speed_mph': speed * 2.2369362921,
                    'velocity_mps': [vv.x, vv.y, vv.z], 'control': request}) + '\n')
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'subject_actor_id': subject.id,
                    'curbside_actor_id': curbside.id,
                    'subject_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
                    'curbside_xyz_m': [curb_pose.location.x,
                                       curb_pose.location.y, curb_pose.location.z],
                    'observed_speed_mps': speed, 'requested_control': request,
                    'requested_activity': config.get('activity_request'),
                    'camera_native_frames': camera_frames,
                    'legal_outcome_verified': False}) + '\n')
                bodies.write(json.dumps({'source_kind': 'original_actor_body_footprints',
                    'frame': index, 'native_frame': native_frame, 'time_s': time_s,
                    'actors': {'ego': {'actor_id': subject.id,
                                       'footprint_corners_xy_m': footprint(subject)},
                               'curbside': {'actor_id': curbside.id,
                                            'footprint_corners_xy_m': footprint(curbside)}}}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        complete = True
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'subject_actor_id': subject.id, 'curbside_actor_id': curbside.id,
                'original_context_review_required': True, 'legal_outcome_claimed': False}
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
        restoration = restore(client, saved) if changed else {
            'restored': True, 'world_unchanged': True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                context={'case_id': config['case_id'],
                         'candidate_id': config.get('candidate_id', 'primary'),
                         'highway_activity_exception_review': 'pending'})


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
