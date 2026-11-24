"""Original Native bus and traffic acquisition draft; loading/activity sources pending."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from entry import FRAMES, RATE_HZ, WHEEL_GAP_M, target
from geometry import CURB_FACE_Y_M, check as geometry_check, open_drive

CAMERAS = ('overview', 'bus_front', 'curb_wheel', 'traffic_rear')


def check(config):
    geometry = geometry_check()
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C149507', 'LVMC-11-60-030-A4', 'bus_driver'):
        raise ValueError('exact assignment identity changed')
    if config['bus_case'] not in WHEEL_GAP_M or config['case_id'].rsplit('__', 1)[-1] not in ('probe_1', 'probe_2'):
        raise ValueError('unknown exact bus case')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != FRAMES / RATE_HZ:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four original source cameras required')
    return {'geometry': geometry, 'frames': FRAMES, 'camera_names': CAMERAS,
            'native_imported': False, 'bus_classification_observed': False,
            'physical_acceptance_claimed': False}


def survey(carla, mapping):
    points = []
    for x in (-50, -20, 15, 20, 25, 50):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-2.5, z=1.4),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1 or abs(wp.transform.location.x - x) > 1:
            raise RuntimeError('Native one-way curb lane survey failed')
        points.append({'x_m': x, 'road_id': wp.road_id, 'lane_id': wp.lane_id,
                       'native_xyz_m': [wp.transform.location.x, wp.transform.location.y,
                                        wp.transform.location.z]})
    return points


def right_front_wheel_local(bus):
    wheels = bus.get_physics_control().wheels
    if len(wheels) < 4:
        raise RuntimeError('Native bus front-wheel geometry absent')
    front = max(w.position.x for w in wheels)
    candidates = [w for w in wheels if abs(w.position.x - front) < 1]
    if len(candidates) < 2:
        raise RuntimeError('Right front wheel cannot be identified')
    wheel = min(candidates, key=lambda w: w.position.y)
    return wheel.position.x / 100.0, wheel.position.y / 100.0


def wheel_contact_y(bus, wheel_local):
    pose = bus.get_transform()
    yaw = math.radians(pose.rotation.yaw)
    return pose.location.y + wheel_local[0] * math.sin(yaw) + wheel_local[1] * math.cos(yaw)


def bus_control(config, frame, bus, wheel_local):
    request = target(config['bus_case'], frame)
    pose, velocity = bus.get_transform(), bus.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    wheel_gap = wheel_contact_y(bus, wheel_local) - CURB_FACE_Y_M
    lateral_error = request['target_right_front_wheel_gap_m'] - wheel_gap
    remaining = request['target_x_m'] - pose.location.x
    brake = 1.0 if remaining < 1 and speed < 1 else (.55 if remaining < speed * speed / 4 + 2 else 0.0)
    throttle = 0.0 if brake else max(0, min(.35, .23 + .08 * (request['target_speed_mps'] - speed)))
    steer = max(-.22, min(.22, .08 * lateral_error))
    return {'throttle': throttle, 'brake': brake, 'steer': steer,
            'target_right_front_wheel_gap_m': request['target_right_front_wheel_gap_m'],
            'target_x_m': request['target_x_m'], 'loading_requested': request['loading_requested']}


def execute(config, output_dir, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'bus-traffic-poses.jsonl').exists():
        raise ValueError('new materialized attempt required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('exclusive idle Native world required')
    owned, encoders, camera_queues = [], {}, {}
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        readback = survey(carla, world.get_map())
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        library = world.get_blueprint_library()
        buses = library.filter('vehicle.mitsubishi.fusorosa')
        if not buses:
            raise RuntimeError('Exact Native bus blueprint unavailable')
        bus_bp = buses[0]
        bus_bp.set_attribute('role_name', 'c149507_bus_classification_pending')
        bus = world.spawn_actor(bus_bp, carla.Transform(
            carla.Location(x=-20, y=-3.5, z=2), carla.Rotation(yaw=0)))
        owned.append(bus)
        wheel_local = right_front_wheel_local(bus)
        traffic_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        traffic_bp.set_attribute('role_name', 'c149507_other_vehicle')
        traffic = world.spawn_actor(traffic_bp, carla.Transform(
            carla.Location(x=-45, y=-2.5, z=2), carla.Rotation(yaw=0)))
        owned.append(traffic)
        (output / 'bus-zone-inventory.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C149507',
            'native_lane_survey': readback, 'curb_face_y_m': CURB_FACE_Y_M,
            'right_front_wheel_local_xy_m': list(wheel_local),
            'bus_blueprint_id': bus.type_id,
            'non_tour_bus_classification_source': None, 'public_street_source': None,
            'qualifying_location_source': None, 'loading_activity_source': None}, indent=2) + '\n')
        mounts = {'overview': (20, -20, 24, -35), 'bus_front': (22, -11, 9, -20),
                  'curb_wheel': (20, -8, 5, -25), 'traffic_rear': (-25, 7, 10, -20)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            cbp = library.find('sensor.camera.rgb')
            cbp.set_attribute('image_size_x', str(spec['width']))
            cbp.set_attribute('image_size_y', str(spec['height']))
            cbp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            camera = world.spawn_actor(cbp, carla.Transform(
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
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'bus-traffic-poses.jsonl').open('x') as poses:
            initial_time = None
            for index in range(FRAMES):
                request = bus_control(config, index, bus, wheel_local)
                bus.apply_control(carla.VehicleControl(
                    throttle=request['throttle'], brake=request['brake'], steer=request['steer']))
                traffic.apply_control(carla.VehicleControl(throttle=.22, brake=0, steer=0))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                camera_frames = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                bt, bv, ot, ov = bus.get_transform(), bus.get_velocity(), traffic.get_transform(), traffic.get_velocity()
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'bus_id': bus.id, 'other_vehicle_id': traffic.id,
                    'bus_xyz_m': [bt.location.x, bt.location.y, bt.location.z],
                    'bus_yaw_deg': bt.rotation.yaw, 'other_vehicle_xyz_m': [ot.location.x, ot.location.y, ot.location.z],
                    'bus_observed_speed_mps': math.hypot(bv.x, bv.y),
                    'other_vehicle_observed_speed_mps': math.hypot(ov.x, ov.y),
                    'right_front_wheel_contact_y_m': wheel_contact_y(bus, wheel_local),
                    'requested_control': request, 'camera_native_frames': camera_frames,
                    'loading_activity_observed': False}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'loading_activity_observed': False, 'physical_acceptance_claimed': False}
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
