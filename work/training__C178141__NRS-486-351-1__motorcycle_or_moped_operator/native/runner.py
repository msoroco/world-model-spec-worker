"""Original Native adjacent-vehicle acquisition draft; no legal judgment."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive
from route import FRAMES, RATE_HZ, LATERAL_M, target

CAMERAS = ('overview', 'subject_front', 'lane_side', 'traffic_rear')


def check(config):
    geometry = geometry_check()
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C178141', 'NRS-486-351-1', 'motorcycle_or_moped_operator'):
        raise ValueError('exact assignment identity changed')
    if config['split_case'] not in LATERAL_M or config['case_id'].rsplit('__', 1)[-1] not in ('probe_1', 'probe_2'):
        raise ValueError('unknown exact split case')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != FRAMES / RATE_HZ:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four original source cameras required')
    return {'geometry': geometry, 'frames': FRAMES, 'camera_names': CAMERAS,
            'native_imported': False, 'physical_clearance_observed': False,
            'legal_outcome_claimed': False}


def survey(carla, mapping):
    observations = []
    for x in (-50, -30, 0, 30, 50):
        for y, lane_id in ((4.5, -1), (1.5, -2)):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=1.4),
                                      project_to_road=True, lane_type=carla.LaneType.Driving)
            if wp is None or wp.road_id != 1 or wp.lane_id != lane_id or abs(wp.transform.location.x - x) > 1:
                raise RuntimeError('Native adjacent-lane survey failed')
            observations.append({'x_m': x, 'y_m': y, 'road_id': wp.road_id,
                                 'lane_id': wp.lane_id})
    return observations


def footprint(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if not vertices:
        raise RuntimeError('Native body vertices missing')
    return {'min_x': min(p.x for p in vertices), 'max_x': max(p.x for p in vertices),
            'min_y': min(p.y for p in vertices), 'max_y': max(p.y for p in vertices)}


def control(config, frame, subject):
    request = target(config['split_case'], frame)
    pose, velocity = subject.get_transform(), subject.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    lateral_error = request['y_m'] - pose.location.y
    throttle = max(0.0, min(.35, .2 + .1 * (request['target_speed_mps'] - speed)))
    brake = .2 if speed > request['target_speed_mps'] + .5 else 0.0
    steer = max(-.25, min(.25, .1 * lateral_error))
    return {'throttle': throttle, 'brake': brake, 'steer': steer,
            'requested_x_m': request['x_m'], 'requested_y_m': request['y_m'],
            'requested_speed_mps': request['target_speed_mps']}


def execute(config, output_dir, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'actor-poses.jsonl').exists():
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
        motorcycles = library.filter('vehicle.kawasaki.ninja')
        if not motorcycles:
            raise RuntimeError('Exact Native motorcycle blueprint unavailable')
        motorcycle_bp = motorcycles[0]
        motorcycle_bp.set_attribute('role_name', 'c178141_motorcycle_subject')
        subject = world.spawn_actor(motorcycle_bp, carla.Transform(
            carla.Location(x=-30, y=LATERAL_M[config['split_case']], z=2),
            carla.Rotation(yaw=0)))
        owned.append(subject)
        other_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        others = []
        for y, label in ((1.5, 'lower_lane'), (4.5, 'upper_lane')):
            other_bp.set_attribute('role_name', 'c178141_' + label)
            car = world.spawn_actor(other_bp, carla.Transform(
                carla.Location(x=0, y=y, z=2), carla.Rotation(yaw=0)))
            car.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
            owned.append(car)
            others.append(car)
        (output / 'lane-inventory.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C178141',
            'lane_survey': readback, 'subject_blueprint_id': subject.type_id,
            'other_vehicle_ids': [car.id for car in others],
            'police_duty_source': None, 'physical_collision_clearance_verified': False}, indent=2) + '\n')
        mounts = {'overview': (0, -22, 24, -35), 'subject_front': (-13, -8, 8, -15),
                  'lane_side': (0, 12, 10, -20), 'traffic_rear': (-22, 12, 10, -20)}
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
                (output / 'actor-poses.jsonl').open('x') as poses:
            initial_time = None
            for index in range(FRAMES):
                request = control(config, index, subject)
                subject.apply_control(carla.VehicleControl(
                    throttle=request['throttle'], brake=request['brake'], steer=request['steer']))
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
                vt = subject.get_transform()
                speeds = [math.hypot(car.get_velocity().x, car.get_velocity().y) for car in others]
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'subject_id': subject.id,
                    'subject_xyz_m': [vt.location.x, vt.location.y, vt.location.z],
                    'subject_footprint_m': footprint(subject),
                    'other_vehicle_ids': [car.id for car in others],
                    'other_vehicle_footprints_m': [footprint(car) for car in others],
                    'other_vehicle_speeds_mps': speeds,
                    'requested_control': request, 'camera_native_frames': camera_frames,
                    'physical_collision_clearance_verified': False}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'physical_collision_clearance_verified': False, 'legal_outcome_claimed': False}
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
