"""Original Native private-way entry capture; --check stays CPU-only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys

from geometry import check as geometry_check, open_drive, PRIVATE_X_M, HIGHWAY_Y_M

FRAMES = 600
RATE_HZ = 20
CAMERAS = (('overview', 1920, 1080, 5, -15, 26),
           ('approach', 1280, 720, -42, -8, 7),
           ('reference_corner', 1280, 720, 10, -9, 7),
           ('driver_reference', 1280, 720, 3, -33, 4))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle / 'config.json').read_text())
    selection = json.loads((bundle / 'candidate-selection.json').read_text())
    if (config['selected_case_id'] != config['case_id'] or
            config['case_id'] not in config['supported_case_ids'] or
            selection['case_id'] != config['case_id'] or
            selection['candidate_id'] != config['candidate_id'] or
            selection['construction_sha256'] != digest(bundle / 'construction.json')):
        raise ValueError('Materialized case/candidate/construction mismatch')
    if config['law_id'] != 'NRS-484B-260' or config['cell_id'] != 'C177626':
        raise ValueError('Frozen legal cell mismatch')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != 30:
        raise ValueError('Original capture rate or duration changed')
    if len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('Four cameras required')
    geometry_check()
    return config


def actor_row(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    body = sorted({(round(point.x, 5), round(point.y, 5)) for point in vertices})
    if len(body) != 4:
        raise RuntimeError('Original vehicle body lacks four ground corners')
    return {'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'center_xy_m': [transform.location.x, transform.location.y],
            'body_xy_m': [list(point) for point in body],
            'velocity_xy_mps': [velocity.x, velocity.y],
            'speed_mps': math.hypot(velocity.x, velocity.y)}


def execute(output, host, port):
    bundle = Path(__file__).resolve().parent
    config = source_check(bundle)
    repo = next((p for p in Path(__file__).resolve().parents if (p / 'batch.json').is_file()), None)
    if repo is None:
        raise RuntimeError('Worker runtime root absent')
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    sys.path.insert(1, str(repo / 'runtime/python'))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Use fresh original attempt directory')
    output.mkdir(parents=True)
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old_world.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous world required')
    owned, encoders, queues = [], {}, {}
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=50, wall_height=0, additional_width=0,
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
        mapping = world.get_map()
        surveyed = {}
        for name, xyz, road_id, lane_id in (
            ('highway_west', (-35, HIGHWAY_Y_M, .5), 1, -1),
            ('highway_conflict', (PRIVATE_X_M, HIGHWAY_Y_M, .5), 1, -1),
            ('private_way', (PRIVATE_X_M, -25, .5), 2, -1),
        ):
            waypoint = mapping.get_waypoint(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                                            project_to_road=False, lane_type=carla.LaneType.Driving)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (road_id, lane_id):
                raise RuntimeError('Original Native road/lane survey differs: ' + name)
            surveyed[name] = {'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                              'lane_width_m': waypoint.lane_width}
        blueprints = world.get_blueprint_library()
        vehicle_bp = blueprints.find('vehicle.tesla.model3')
        actors = {}
        for name, x, y, yaw in (('ego', PRIVATE_X_M, -27, 90),
                                ('approach_1', -49, HIGHWAY_Y_M, 0),
                                ('approach_2', -76, HIGHWAY_Y_M, 0)):
            vehicle_bp.set_attribute('role_name', 'c177626_' + name)
            actor = world.spawn_actor(vehicle_bp, carla.Transform(
                carla.Location(x=x, y=y, z=.7), carla.Rotation(yaw=yaw)))
            owned.append(actor)
            actors[name] = actor
        for name, width, height, x, y, z in CAMERAS:
            if config['candidate_id'] == 'fallback1' and name in ('approach', 'reference_corner'):
                x, z = x - 6, z + 3
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', '.05')
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=-45 if z > 10 else -15)))
            owned.append(camera)
            frames = queue.Queue()
            camera.listen(frames.put)
            queues[name] = frames
            process = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}', '-r', '20',
                '-i', '-', '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            encoders[name] = process
        rows_path = output / 'private-entry-actors.jsonl'
        yield_case = config['case_id'].endswith('__probe_a')
        with PipelineCapture(client, actors['ego'], output, config['case_id'],
                             required_observations=[]) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                rows_path.open('x') as rows:
            for index in range(FRAMES):
                # Engineering control distinguishes early entry from waiting; actual order is measured.
                actors['approach_1'].set_target_velocity(carla.Vector3D(x=8, y=0, z=0))
                actors['approach_2'].set_target_velocity(carla.Vector3D(x=8, y=0, z=0))
                target = 0 if index < (250 if yield_case else 30) else 4
                actors['ego'].set_target_velocity(carla.Vector3D(x=0, y=target, z=0))
                native_frame = world.tick()
                all_vehicles = {str(a.id): actor_row(a) for a in world.get_actors().filter('vehicle.*')}
                selected = {name: actor_row(actor) for name, actor in actors.items()}
                if set(a['actor_id'] for a in selected.values()) != set(map(int, all_vehicles)):
                    raise RuntimeError('Uninventoried approaching vehicle in exclusive world')
                rows.write(json.dumps({'native_frame': native_frame, 'video_frame': index,
                    'time_s': index / RATE_HZ, 'actors': selected,
                    'all_vehicle_bodies': all_vehicles}) + '\n')
                camera_frames = {}
                for name, _, _, _, _, _ in CAMERAS:
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera frame join differs')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, index / RATE_HZ,
                                 camera_native_frames=camera_frames)
                capture.capture(native_frame, index / RATE_HZ,
                                extra={'video_frame': index,
                                       'all_vehicle_ids': sorted(all_vehicles)})
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + error.decode()[-400:])
        (output / 'road.xodr').write_text(open_drive())
        (output / 'private-entry-context.json').write_text(json.dumps({
            'source_kind': 'original_native_private_way_entry',
            'case_id': config['case_id'], 'native_map_survey': surveyed,
            'all_vehicle_inventory_method': 'every world vehicle actor body each frame',
            'physical_and_legal_acceptance_claimed': False,
        }, indent=2) + '\n')
        source_names = ('road.xodr', 'private-entry-context.json', 'private-entry-actors.jsonl',
                        'video_frames.jsonl', 'trace.jsonl', 'capture/manifest.json',
                        *(name + '.mkv' for name in queues))
        (output / 'private-entry-review.json').write_text(json.dumps({
            'case_id': config['case_id'], 'source_sha256':
            {name: digest(output / name) for name in source_names},
            'physical_acceptance_claimed': False,
        }, indent=2) + '\n')
        return {'frames': FRAMES, 'camera_names': list(queues),
                'physical_acceptance_claimed': False}
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                actor.stop() if hasattr(actor, 'stop') else None
                actor.destroy()
            except Exception:
                pass
        if changed:
            restore(client, saved)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(geometry_check()))
    else:
        if args.output_dir is None or args.host is None or args.port is None:
            raise SystemExit('Native execution requires output directory, host and port')
        print(json.dumps(execute(args.output_dir, args.host, args.port)))
