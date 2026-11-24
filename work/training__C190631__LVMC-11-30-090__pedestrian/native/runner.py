"""Survey-gated original Native overpass pedestrian capture."""
import argparse
import json
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, geometry, open_drive

FRAMES = 600
RATE = 20
CAMERAS = (
    ('overview', 1280, 720, 0, -14, 24, -55),
    ('along_roadway', 1280, 720, -38, -11, 13, -18),
    ('sidewalk', 1280, 720, 0, -13, 14, -40),
    ('pedestrian_close', 1280, 720, 28, -10, 12, -30),
)


def check():
    g = geometry_check()
    if len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4 or FRAMES / RATE != 30:
        raise ValueError('four independent camera streams and 30-second capture required')
    return {'passed': True, 'frames': FRAMES, 'rate_hz': RATE,
            'cameras': [c[0] for c in CAMERAS], 'geometry': g,
            'native_imported': False, 'physical_acceptance_claimed': False}


def survey(world, carla):
    mapping = world.get_map()
    output = {}
    for name, y, kind, lane_id in (('roadway', -1.75, carla.LaneType.Driving, -1),
                                   ('sidewalk', -5, carla.LaneType.Sidewalk, -3)):
        samples = []
        for x in (-30, 0, 30):
            location = carla.Location(x=x, y=y, z=8.4)
            wp = mapping.get_waypoint(location, project_to_road=True, lane_type=kind)
            if wp is None or wp.lane_id != lane_id:
                raise RuntimeError(f'Native {name} lane readback failed at x={x}')
            read = wp.transform.location
            if abs(read.x - x) > 1 or abs(read.y - y) > 1 or abs(read.z - 8) > 1:
                raise RuntimeError(f'Native {name} position/elevation readback failed at x={x}')
            samples.append({'requested_x_m': x, 'native_xyz_m': [read.x, read.y, read.z],
                            'road_id': wp.road_id, 'lane_id': wp.lane_id,
                            'lane_type': str(wp.lane_type)})
        output[name] = samples
    if {r['road_id'] for samples in output.values() for r in samples} != {1}:
        raise RuntimeError('Native sidewalk is not attached to the sampled roadway')
    return output


def execute(output_dir, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    check()
    output = Path(output_dir).resolve()
    if output.exists():
        raise ValueError('choose a fresh original Native attempt directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('requires an exclusive idle asynchronous Native world')
    owned = []
    encoders = {}
    queues = {}
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
        output.mkdir(parents=True)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        surface = geometry()
        surface['native_readback'] = readback
        surface['source_status'] = 'original_native_map_readback'
        (output / 'surface-geometry.json').write_text(json.dumps(surface, indent=2) + '\n')
        blueprints = world.get_blueprint_library()
        walker_bp = sorted(blueprints.filter('walker.pedestrian.*'), key=lambda b: b.id)[0]
        walker_bp.set_attribute('role_name', 'c190631_pedestrian_subject')
        walker = world.spawn_actor(walker_bp, carla.Transform(
            carla.Location(x=-30, y=-1.75, z=8.6), carla.Rotation(yaw=0)))
        owned.append(walker)
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            video = output / (name + '.mkv')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', str(RATE), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(video)],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'pedestrian-poses.jsonl').open('x') as poses:
            first_elapsed = None
            for index in range(FRAMES):
                walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=1, y=0, z=0), speed=2))
                native_frame = world.tick()
                snapshot_frame = world.get_snapshot()
                if snapshot_frame.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame identity differs')
                ts = snapshot_frame.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = ts
                elapsed = ts - first_elapsed
                transform = walker.get_transform()
                velocity = walker.get_velocity()
                mapped = {}
                for name in queues:
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError(f'Original camera frame join failed: {name}')
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, elapsed, camera_native_frames=mapped)
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': elapsed,
                    'native_elapsed_seconds': ts,
                    'pedestrian_xy_m': [transform.location.x, transform.location.y],
                    'pedestrian_z_m': transform.location.z,
                    'velocity_xy_mps': [velocity.x, velocity.y],
                    'walker_actor_id': walker.id,
                    'walker_blueprint_id': walker.type_id}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError(f'Original camera encoding failed: {name}: {stderr.decode()[-400:]}')
        return {'frames': FRAMES, 'camera_names': list(queues),
                'native_survey': readback, 'physical_acceptance_claimed': False}
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
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check == args.execute:
        raise SystemExit('choose exactly one of --check or --execute')
    if args.execute and not args.output_dir:
        raise SystemExit('--output-dir required for Native execution')
    print(json.dumps(check() if args.check else execute(args.output_dir, args.host, args.port)))
