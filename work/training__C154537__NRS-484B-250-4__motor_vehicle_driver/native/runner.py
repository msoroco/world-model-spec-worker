"""Original Native one-way junction attempt; only --check runs on CPU."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from check import check as request_check

CAMERAS = (('overview', 1280, 720, 0, -18, 25, -70),
           ('ego_approach', 1280, 720, -30, -8, 7, -30),
           ('cross_approach', 1280, 720, 8, -30, 7, -30),
           ('driver_view', 1280, 720, -9, -1.75, 3, -5))
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    result = request_check()
    root = Path.cwd()
    import xml.etree.ElementTree as ET
    tree = ET.fromstring((root / 'crossroads.xodr').read_text())
    roads = tree.findall('road')
    if {int(road.get('id')) for road in roads} != {250, 251, 252, 253, 254, 255}:
        raise ValueError('Exact one-way junction roads missing')
    if any(road.findall('lanes/laneSection/left/lane') for road in roads):
        raise ValueError('Opposing lanes violate one-way cell')
    if len(tree.findall('.//signal')) != 2 or tree.findall('.//object'):
        raise ValueError('Two uncovered heads and no physical crossing marks required')
    if len(CAMERAS) != 4 or len({row[0] for row in CAMERAS}) != 4:
        raise ValueError('Four original cameras required')
    result['map_sha256'] = sha(root / 'crossroads.xodr')
    result['native_junction_observed'] = False
    return result


def actor_row(actor):
    transform = actor.get_transform(); velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    return {'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'center_xyz_m': [transform.location.x, transform.location.y, transform.location.z],
            'body_xyz_m': [[p.x, p.y, p.z] for p in vertices],
            'velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)}


def execute(output, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    check()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Use a fresh original Native attempt directory')
    client = carla.Client(host, port); client.set_timeout(180)
    previous = client.get_world(); saved = snapshot(client)
    if previous.get_settings().synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for actor in previous.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    output.mkdir(parents=True)
    owned, queues, encoders = [], {}, {}
    changed = False
    try:
        source_road = Path('crossroads.xodr')
        world = client.generate_opendrive_world(source_road.read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings(); settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05; settings.substepping = True
        settings.max_substep_delta_time = .01; settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        for road_id, station in ((250, 40), (251, 6), (252, 10),
                                 (253, 40), (254, 6), (255, 10)):
            waypoint = mapping.get_waypoint_xodr(road_id, -1, station)
            if waypoint is None or waypoint.lane_type != carla.LaneType.Driving:
                raise RuntimeError('Native one-way driving lane readback failed: ' + str(road_id))
        lights = {str(light.get_opendrive_id()): light for light in
                  world.get_actors().filter('traffic.traffic_light*')}
        if not {'c154537-head-ego', 'c154537-head-cross'} <= set(lights):
            raise RuntimeError('Native installed signal heads missing from authored OpenDRIVE')
        for light in lights.values():
            light.set_state(carla.TrafficLightState.Off)
            light.freeze(True)
        blueprints = world.get_blueprint_library()
        ego = world.try_spawn_actor(blueprints.find('vehicle.tesla.model3'),
            carla.Transform(carla.Location(x=-35, y=-1.75, z=1.5), carla.Rotation(yaw=0)))
        other = world.try_spawn_actor(blueprints.find('vehicle.audi.tt'),
            carla.Transform(carla.Location(x=1.75, y=-35, z=1.5), carla.Rotation(yaw=90)))
        if ego is None or other is None:
            raise RuntimeError('Original actor spawn failed')
        owned.extend((ego, other))
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 85), ('sensor_tick', .05)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=pitch, yaw=90 if name == 'cross_approach' else 0)))
            owned.append(sensor)
            received = queue.Queue(); sensor.listen(received.put); queues[name] = received
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                '-s', f'{width}x{height}', '-r', '20', '-i', '-', '-frames:v',
                str(FRAMES), '-c:v', 'ffv1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        requests = [json.loads(line) for line in Path('request.jsonl').read_text().splitlines()]
        with (output / 'native-motion.jsonl').open('x') as motion, FrameMap(output / 'video_frames.jsonl') as frame_map:
            for index, request in enumerate(requests):
                target_speed = 0 if index and request['ego_center_xy_m'][0] == requests[index-1]['ego_center_xy_m'][0] else 4
                ego.set_target_velocity(carla.Vector3D(x=target_speed, y=0, z=0))
                other.set_target_velocity(carla.Vector3D(x=0, y=4 if index < 350 else 0, z=0))
                native_frame = world.tick()
                ego_source, other_source = actor_row(ego), actor_row(other)
                state = 'inoperative_dark' if all(light.get_state() == carla.TrafficLightState.Off for light in lights.values()) else 'changed'
                pose = {'native_frame': native_frame, 'video_frame': index, 'time_s': index / 20,
                    'ego_center_x_m': ego_source['center_xyz_m'][0],
                    'ego_front_x_m': max(vertex[0] for vertex in ego_source['body_xyz_m']),
                    'ego_speed_mps': ego_source['speed_mps'],
                    'ego': ego_source, 'other': other_source,
                    'signal_id': 'c154537-head-ego', 'signal_state': state,
                    'source_kind': 'original_native', 'legal_verdict': None}
                motion.write(json.dumps(pose, allow_nan=False) + '\n')
                camera_frames = {}
                for name, *_ in CAMERAS:
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera/native join failed')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, index / 20, camera_native_frames=camera_frames)
        for name, process in encoders.items():
            process.stdin.close(); stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + stderr.decode()[-400:])
        (output / 'crossroads.xodr').write_text(source_road.read_text())
        (output / 'scene-survey.json').write_text(json.dumps({
            'source_kind': 'original_native', 'road_sha256': sha(source_road),
            'stop_line_present': False, 'near_side_crosswalk_present': False,
            'sidewalk_derived_crosswalk_reviewed': False,
            'signal_installed': True, 'signal_uncovered': True,
            'official_device_provenance_reviewed': False,
            'through_highway_provenance_reviewed': False,
            'signal_id': 'c154537-head-ego',
            'ego_front_offset_m': None, 'intersection_entry_front_x_m': -6.0,
            'driver_view_samples': [],
            'review_pending': ['original painted geometry and sidewalks',
                'official signal provenance', 'through highway', 'driver view rays']}, indent=2) + '\n')
        return {'frames': FRAMES, 'camera_names': list(queues),
                'source_review_complete': False, 'physical_acceptance_claimed': False}
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill(); process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'): actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restore(client, saved)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        if args.output_dir is None:
            parser.error('Native output directory required')
        print(json.dumps(execute(args.output_dir, args.host, args.port)))
