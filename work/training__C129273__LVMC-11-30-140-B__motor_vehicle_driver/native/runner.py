"""Original Native C129273 capture draft; marker appearance needs independent review."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = ('overview', 'approach', 'person', 'driver_side')


def check(config):
    geometry = geometry_check()
    if config['case_id'].rsplit('__', 1)[-1] not in ('probe_1', 'probe_2'):
        raise ValueError('unknown selected case')
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C129273', 'LVMC-11-30-140-B', 'motor_vehicle_driver'):
        raise ValueError('source identity changed')
    if config['rate_hz'] != RATE or config['duration_s'] != 30:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four source cameras required')
    return {'geometry': geometry, 'camera_names': CAMERAS, 'frames': FRAMES,
            'native_imported': False, 'physical_acceptance_claimed': False}


def survey(carla, mapping):
    points = []
    for x in (-80, -40, 0, 40, 80):
        z = 25 + .025 * (x + 120) + .5
        wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=z),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1 or abs(wp.transform.location.x - x) > 1:
            raise RuntimeError('Native mountain-road lane survey failed')
        points.append({'x_m': x, 'road_id': wp.road_id, 'lane_id': wp.lane_id,
                       'native_xyz_m': [wp.transform.location.x, wp.transform.location.y,
                                        wp.transform.location.z]})
    return points


def execute(config, output_dir, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'vehicle-person-poses.jsonl').exists():
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
        settings.fixed_delta_seconds = 1 / RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        readback = survey(carla, world.get_map())
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'road-survey.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C129273',
            'lane_survey': readback, 'marker_appearance_verified': False}, indent=2) + '\n')
        library = world.get_blueprint_library()
        vehicle_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        vehicle_bp.set_attribute('role_name', 'c129273_subject_driver')
        vehicle = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-80, y=-1.75, z=26.5), carla.Rotation(yaw=0)))
        owned.append(vehicle)
        walker_bp = sorted(library.filter('walker.pedestrian.*'), key=lambda b: b.id)[0]
        walker = world.spawn_actor(walker_bp, carla.Transform(
            carla.Location(x=0, y=-4.6, z=28.1), carla.Rotation(yaw=90)))
        owned.append(walker)
        mounts = {'overview': (-12, -24, 40, -35), 'approach': (-34, -12, 32, -15),
                  'person': (3, -11, 31, -15), 'driver_side': (-7, 8, 33, -20)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            bp = library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(spec['width']))
            bp.set_attribute('image_size_y', str(spec['height']))
            bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(bp, carla.Transform(
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
                (output / 'vehicle-person-poses.jsonl').open('x') as poses:
            initial_time = None
            for index in range(FRAMES):
                # Controller targets are engineering requests; observed motion is saved below.
                stopping_case = config['case_id'].endswith('probe_1')
                x = vehicle.get_transform().location.x
                brake = 1.0 if stopping_case and x > -15 else 0.0
                throttle = 0.0 if brake else .25
                vehicle.apply_control(carla.VehicleControl(throttle=throttle, brake=brake))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                images = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    images[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=images)
                vt, vv, wt = vehicle.get_transform(), vehicle.get_velocity(), walker.get_transform()
                extent = vehicle.bounding_box.extent
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'vehicle_id': vehicle.id, 'person_id': walker.id,
                    'vehicle_xyz_m': [vt.location.x, vt.location.y, vt.location.z],
                    'person_xyz_m': [wt.location.x, wt.location.y, wt.location.z],
                    'vehicle_yaw_deg': vt.rotation.yaw,
                    'bbox_half_length_m': extent.x, 'bbox_half_width_m': extent.y,
                    'speed_mps': math.sqrt(vv.x * vv.x + vv.y * vv.y + vv.z * vv.z),
                    'requested_throttle': throttle, 'requested_brake': brake,
                    'marker_appearance_verified': False}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'marker_appearance_verified': False, 'physical_acceptance_claimed': False}
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
