"""Survey-gated original Native crosswalk parking capture."""
import argparse
import json
from pathlib import Path
import queue
import subprocess

from geometry import CROSSWALK_RECT, TARGET_X, check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = (
    ('overview', 1920, 1080, 0, -19, 25, -45),
    ('approach', 1280, 720, 3, -15, 14, -35),
    ('reference_corner', 1280, 720, -20, -15, 14, -35),
    ('driver_reference', 1280, 720, -5, -10, 9, -25),
)


def control_for(case, index, distance, speed):
    """Engineering motion intent only; legal stop/stand/park is source reviewed."""
    if case == 'stop_near' and index >= 300:
        return {'throttle': .25, 'brake': 0.0, 'hand_brake': False}
    throttle = .28 if distance > 9 else (.11 if distance > 4 else 0.0)
    brake = 0.0 if distance > 4 else (1.0 if distance < 2 else .35)
    return {'throttle': throttle, 'brake': brake,
            'hand_brake': case in ('controlled_1', 'controlled_2', 'boundary_20ft')
            and distance < 2 and speed < .1}


def check():
    g = geometry_check()
    if len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4 or FRAMES / RATE != 30:
        raise ValueError('four independent camera streams and 30-second capture required')
    return {'passed': True, 'frames': FRAMES, 'rate_hz': RATE,
            'camera_names': [c[0] for c in CAMERAS], 'targets': TARGET_X,
            'geometry': g, 'native_imported': False, 'physical_acceptance_claimed': False}


def survey(world, carla):
    mapping = world.get_map()
    out = []
    for x in (-30, -14, -5, 3, 30):
        loc = carla.Location(x=x, y=-5.0, z=8.4)
        wp = mapping.get_waypoint(loc, project_to_road=True, lane_type=carla.LaneType.Parking)
        if wp is None or wp.road_id != 1 or wp.lane_id != -2:
            raise RuntimeError(f'Native parking lane readback failed at x={x}')
        at = wp.transform.location
        if abs(at.x - x) > 1 or abs(at.y + 5.0) > 1 or abs(at.z - 8) > 1:
            raise RuntimeError(f'Native parking geometry readback failed at x={x}')
        out.append({'requested_x_m': x, 'native_xyz_m': [at.x, at.y, at.z],
                    'road_id': wp.road_id, 'lane_id': wp.lane_id, 'lane_type': str(wp.lane_type)})
    return out


def survey_crosswalk(world):
    points = world.get_map().get_crosswalks()
    near = [[p.x, p.y, p.z] for p in points if -2 <= p.x <= 6 and -8.5 <= p.y <= 2]
    if len(near) < 4:
        raise RuntimeError('Native marked-crosswalk geometry readback missing')
    xs, ys = [p[0] for p in near], [p[1] for p in near]
    if (abs(min(xs) - CROSSWALK_RECT[0]) > .5 or
            abs(max(xs) - CROSSWALK_RECT[1]) > .5 or
            abs(min(ys) - CROSSWALK_RECT[2]) > .5 or
            abs(max(ys) - CROSSWALK_RECT[3]) > .5):
        raise RuntimeError('Native crosswalk extent differs from distance reference')
    return near


def execute(output_dir, case, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    check()
    if case not in TARGET_X:
        raise ValueError('unknown crosswalk parking case')
    output = Path(output_dir).resolve()
    if any((output / name).exists() for name in ('video_frames.jsonl', 'vehicle-poses.jsonl')):
        raise ValueError('original Native attempt already has frame sources')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('requires an exclusive idle asynchronous Native world')
    owned, encoders, queues = [], {}, {}
    changed = False
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
        readback = survey(world, carla)
        crosswalk_readback = survey_crosswalk(world)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        inventory = {'assignment_id': 'training__C229397__LVMC-11-52-130-A12__motor_vehicle_driver',
                          'source_kind': 'native_saved_sample', 'native_readback': readback,
                          'native_crosswalk_readback': crosswalk_readback,
                          'crosswalk_rect_xyxy_m': CROSSWALK_RECT,
                          'crosswalk_road_object_id': '1',
                          'jurisdiction_source_id': None,
                          'marked_crosswalk_source_id': None,
                          'crosswalk_extent_source_id': 'Native map.get_crosswalks and road.xodr',
                          'responsible_person_source_id': None,
                          'traffic_conflict_review_source_id': None,
                          'law_compliance_review_source_id': None,
                          'directions_review_source_id': None,
                          'source_status': 'Native proposed geometry only; marked paint and exception contexts need original source review'}
        (output / 'crosswalk-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
        bp = sorted(world.get_blueprint_library().filter('vehicle.*'), key=lambda b: b.id)[0]
        bp.set_attribute('role_name', 'c229397_parking_subject')
        vehicle = world.spawn_actor(bp, carla.Transform(carla.Location(x=-38, y=-5.0, z=8.8), carla.Rotation(yaw=0)))
        owned.append(vehicle)
        for name, width, height, x, y, z, pitch in CAMERAS:
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', str(width))
            camera_bp.set_attribute('image_size_y', str(height))
            camera_bp.set_attribute('fov', '85')
            camera_bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', str(RATE), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'vehicle-poses.jsonl').open('x') as poses, (output / 'control-intent.jsonl').open('x') as intent, (output / 'trace.jsonl').open('x') as trace:
            first_elapsed = None
            for index in range(FRAMES):
                location = vehicle.get_transform().location
                velocity = vehicle.get_velocity()
                distance = TARGET_X[case] - location.x
                # Engineering brake schedule only; actual parking is measured after capture.
                speed_before = (velocity.x**2 + velocity.y**2 + velocity.z**2)**.5
                command = control_for(case, index, distance, speed_before)
                vehicle.apply_control(carla.VehicleControl(**command, steer=0))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame identity differs')
                ts = snap.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = ts
                elapsed = ts - first_elapsed
                transform = vehicle.get_transform()
                velocity = vehicle.get_velocity()
                bbox = vehicle.bounding_box.extent
                mapped = {}
                for name, q in queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError(f'Original camera frame join failed: {name}')
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, elapsed, camera_native_frames=mapped)
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': elapsed, 'vehicle_id': vehicle.id,
                    'vehicle_xy_m': [transform.location.x, transform.location.y],
                    'yaw_rad': transform.rotation.yaw * 3.141592653589793 / 180,
                    'bbox_half_length_m': bbox.x, 'bbox_half_width_m': bbox.y,
                    'speed_mps': (velocity.x**2 + velocity.y**2 + velocity.z**2)**.5,
                    'native_elapsed_seconds': ts, 'blueprint_id': vehicle.type_id}) + '\n')
                intent.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': elapsed, 'vehicle_id': vehicle.id,
                    'engineering_action': case, 'applied_control': command}) + '\n')
                trace.write(json.dumps({'frame': native_frame, 'time_s': elapsed,
                    'position': {'x': transform.location.x, 'y': transform.location.y,
                                 'z': transform.location.z}, 'heading_deg': transform.rotation.yaw,
                    'speed_mps': (velocity.x**2 + velocity.y**2 + velocity.z**2)**.5}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError(f'Original camera encoding failed: {name}: {stderr.decode()[-400:]}')
        return {'frames': FRAMES, 'camera_names': list(queues), 'native_survey': readback,
                'native_crosswalk_readback': crosswalk_readback,
                'marked_crosswalk_source_missing': True, 'physical_acceptance_claimed': False}
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
            restore(client, saved)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--case', choices=list(TARGET_X))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required for Native execution')
        case = args.case or json.loads(Path('config.json').read_text())['crosswalk_case']
        print(json.dumps(execute(args.output_dir, case, args.host, args.port)))
