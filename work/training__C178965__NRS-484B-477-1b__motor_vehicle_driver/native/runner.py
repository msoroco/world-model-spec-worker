"""Original Native paved-alley parking capture, gated by map readback."""
import argparse
import json
from pathlib import Path
import queue
import subprocess

from geometry import WIDTHS, check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = (
    ('overview', 1280, 720, 0, -17, 24, -45),
    ('along_alley', 1280, 720, -35, -12, 13, -20),
    ('cross_section', 1280, 720, 0, -12, 12, -35),
    ('vehicle_close', 1280, 720, 12, -10, 9, -30),
)


def check(width):
    g = geometry_check(width)
    if len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4 or FRAMES / RATE != 30:
        raise ValueError('four independent cameras and 30-second capture required')
    return {'passed': True, 'frames': FRAMES, 'rate_hz': RATE,
            'camera_names': [c[0] for c in CAMERAS], 'geometry': g,
            'native_imported': False, 'physical_acceptance_claimed': False}


def survey(world, carla, width):
    mapping = world.get_map()
    output = []
    for x in (-30, 0, 30):
        location = carla.Location(x=x, y=-width / 2, z=8.4)
        wp = mapping.get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1:
            raise RuntimeError(f'Native paved alley lane readback failed at x={x}')
        at = wp.transform.location
        if abs(at.x - x) > 1 or abs(wp.lane_width - width) > .2 or abs(at.z - 8) > 1:
            raise RuntimeError(f'Native paved alley width/elevation readback failed at x={x}')
        output.append({'requested_x_m': x, 'native_xyz_m': [at.x, at.y, at.z],
                       'road_id': wp.road_id, 'lane_id': wp.lane_id,
                       'native_lane_width_m': wp.lane_width})
    return output


def _pose(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    extent = actor.bounding_box.extent
    return {'vehicle_id': actor.id,
            'xy_m': [transform.location.x, transform.location.y],
            'yaw_rad': transform.rotation.yaw * 3.141592653589793 / 180,
            'half_length_m': extent.x, 'half_width_m': extent.y,
            'speed_mps': (velocity.x**2 + velocity.y**2 + velocity.z**2)**.5,
            'blueprint_id': actor.type_id}


def execute(output_dir, case, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    if case not in WIDTHS:
        raise ValueError('unknown exact alley case')
    width = WIDTHS[case]
    check(width)
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
        world = client.generate_opendrive_world(open_drive(width), carla.OpendriveGenerationParameters(
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
        readback = survey(world, carla, width)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        inventory = {'assignment_id': 'training__C178965__NRS-484B-477-1b__motor_vehicle_driver',
                     'source_kind': 'native_saved_sample', 'native_readback': readback,
                     'alley_lateral_edges_m': [-width, 0.0],
                     'boundary_measurement_source_id': 'Native map readback plus road.xodr',
                     'public_highway_source_id': None, 'city_block_source_id': None,
                     'rear_access_source_id': None, 'abutting_property_source_id': None,
                     'non_culdesac_source_id': None, 'local_jurisdiction_source_id': None,
                     'local_ordinance_review_source_id': None,
                     'other_alley_scope_review_source_id': None,
                     'source_status': 'original geometry only; alley definition and ordinance need source review'}
        (output / 'alley-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
        library = world.get_blueprint_library()
        bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        bp.set_attribute('role_name', 'c178965_subject')
        subject = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=-38, y=-width + 1, z=8.8), carla.Rotation(yaw=0)))
        owned.append(subject)
        other_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[1]
        other_bp.set_attribute('role_name', 'c178965_other_vehicle')
        other = world.spawn_actor(other_bp, carla.Transform(
            carla.Location(x=0, y=-1, z=8.8), carla.Rotation(yaw=0)))
        owned.append(other)
        for name, image_width, height, x, y, z, pitch in CAMERAS:
            camera_bp = library.find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', str(image_width))
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
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{image_width}x{height}',
                '-r', str(RATE), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'vehicle-poses.jsonl').open('x') as poses:
            first_elapsed = None
            for index in range(FRAMES):
                location = subject.get_transform().location
                distance = -location.x
                throttle = .28 if distance > 9 else (.1 if distance > 4 else 0)
                brake = 0 if distance > 4 else (1 if distance < 2 else .35)
                subject.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=0))
                other.apply_control(carla.VehicleControl(throttle=0, brake=1, hand_brake=True))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame identity differs')
                ts = snap.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = ts
                elapsed = ts - first_elapsed
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
                    'time_s': elapsed, 'subject': _pose(subject), 'other': _pose(other),
                    'native_elapsed_seconds': ts}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError(f'Original camera encoding failed: {name}: {stderr.decode()[-400:]}')
        return {'frames': FRAMES, 'camera_names': list(queues),
                'native_survey': readback, 'legal_alley_status_observed': False,
                'physical_acceptance_claimed': False}
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
    parser.add_argument('--case', choices=list(WIDTHS))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    case = args.case or json.loads(Path('config.json').read_text())['alley_case']
    if args.check:
        print(json.dumps(check(WIDTHS[case])))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required for Native execution')
        print(json.dumps(execute(args.output_dir, case, args.host, args.port)))
