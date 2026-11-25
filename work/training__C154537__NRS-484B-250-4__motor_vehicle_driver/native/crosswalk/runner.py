"""Original Native one-way junction attempt; only --check runs on CPU."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from check import check as request_check

CAMERAS = (('overview', 1920, 1080, 0, -18, 25, -70),
           ('approach', 1280, 720, -30, -8, 7, -30),
           ('reference_corner', 1280, 720, 8, -30, 7, -30),
           ('driver_reference', 1280, 720, -9, -1.75, 3, -5))
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    result = request_check()
    root = Path.cwd()
    tree = ET.fromstring((root / 'crossroads.xodr').read_text())
    roads = tree.findall('road')
    if {int(road.get('id')) for road in roads} != {250, 251, 252, 253, 254, 255}:
        raise ValueError('Exact one-way junction roads missing')
    if any(road.findall('lanes/laneSection/left/lane') for road in roads):
        raise ValueError('Opposing lanes violate one-way cell')
    if len(tree.findall('.//signal')) != 2 or len(tree.findall('.//object')) != 1 or tree.find('.//object').get('type') != 'crosswalk':
        raise ValueError('Two heads and one near-side crosswalk required')
    if len(CAMERAS) != 4 or len({row[0] for row in CAMERAS}) != 4:
        raise ValueError('Four original cameras required')
    result['map_sha256'] = sha(root / 'crossroads.xodr')
    result['native_junction_observed'] = False
    return result


def authored_survey(source_road):
    """Inventory the authored geometry; leave legal road status for source review."""
    root = ET.fromstring(Path(source_road).read_text())
    roads = root.findall('road')
    road_ids = {road.get('id') for road in roads}
    if road_ids != {'250', '251', '252', '253', '254', '255'}:
        raise ValueError('Authored junction road inventory differs')
    objects = [obj for road in roads for obj in road.findall('objects/object')]
    sidewalks = [lane for road in roads for lane in road.findall('.//lane')
                 if lane.get('type') == 'sidewalk']
    marks = [mark.get('type') for road in roads for mark in road.findall('.//roadMark')]
    signals = {signal.get('id'): signal for road in roads
               for signal in road.findall('signals/signal')}
    if len(objects) != 1 or objects[0].get('type') != 'crosswalk' or objects[0].get('id') != '751' or objects[0].get('s') != '51' or sidewalks or any(mark in {'stop', 'crosswalk'} for mark in marks):
        raise ValueError('Authored crosswalk geometry differs')
    if set(signals) != {'701', '702'}:
        raise ValueError('Authored signal inventory differs')
    return {'road_ids': sorted(road_ids), 'objects': len(objects),
            'sidewalk_lanes': len(sidewalks), 'road_mark_types': marks,
            'signal_ids': sorted(signals), 'road_sha256': sha(source_road),
            'authoring_absence_only': False, 'crosswalk_authoring_only': True}


def view_sample(world, ego, other, carla, native_frame):
    """Retain nine rays from a virtual driver eye to the other body's measured pose."""
    ego_pose = ego.get_transform()
    other_pose = other.get_transform()
    eye = ego_pose.transform(carla.Location(x=.5, y=0, z=1.4))
    corners = list(other.bounding_box.get_world_vertices(other_pose))
    center = other_pose.location
    rays = []
    for endpoint in corners + [center]:
        blockers = []
        for hit in world.cast_ray(eye, endpoint):
            if ego.bounding_box.contains(hit.location, ego_pose):
                continue
            if other.bounding_box.contains(hit.location, other_pose):
                continue
            if hit.location.distance(eye) < .05 or hit.location.distance(endpoint) < .02:
                continue
            blockers.append({'label': str(hit.label),
                             'location_m': [hit.location.x, hit.location.y, hit.location.z]})
        rays.append({'endpoint_m': [endpoint.x, endpoint.y, endpoint.z],
                     'blockers': blockers, 'clear': not blockers})
    return {'native_frame': native_frame,
            'center_x_m': ego_pose.location.x,
            'eye_m': [eye.x, eye.y, eye.z],
            'other_actor_id': other.id,
            'approaching_traffic_visible': any(ray['clear'] for ray in rays),
            'rays': rays,
            'method': 'original world.cast_ray to measured other body, virtual eye 1.4 m'}


def signal_readback(lights, carla):
    expected = {'701': (250, -1), '702': (253, -1)}
    observed = {}
    for signal_id, lane in expected.items():
        light = lights.get(signal_id)
        if light is None:
            raise ValueError('Native governing signal missing: ' + signal_id)
        affected = {(point.road_id, point.lane_id)
                    for point in light.get_affected_lane_waypoints()}
        boxes = light.get_light_boxes()
        if lane not in affected or not boxes or light.get_state() != carla.TrafficLightState.Off:
            raise ValueError('Native governing signal/lane/state readback differs: ' + signal_id)
        observed[signal_id] = {'actor_id': light.id, 'state': 'Off',
                               'affected_lanes': sorted([list(item) for item in affected]),
                               'light_box_count': len(boxes),
                               'uncovered_pixels_reviewed': False,
                               'official_authority_inferred': False}
    return observed


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
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap, seal_capture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore
    check()
    output = Path(output).resolve()
    if not output.is_dir() or output != Path.cwd().resolve():
        raise ValueError('Capture requires the materialized exact bundle directory')
    for name in ('native-motion.jsonl', 'trace.jsonl', 'video_frames.jsonl',
                 'scene-survey.json', 'capture-seal.json'):
        if (output / name).exists():
            raise ValueError('Retain previous original acquisition; materialize a fresh bundle')
    client = carla.Client(host, port); client.set_timeout(180)
    previous = client.get_world(); saved = snapshot(client)
    if previous.get_settings().synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for actor in previous.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, queues, encoders = [], {}, {}
    live_capture = None
    changed = False
    restoration = None
    try:
        source_road = Path('crossroads.xodr')
        authored = authored_survey(source_road)
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
        if not {'701', '702'} <= set(lights):
            raise RuntimeError('Native installed signal heads missing from authored OpenDRIVE')
        for light in lights.values():
            light.set_state(carla.TrafficLightState.Off)
            light.freeze(True)
        signal_readback(lights, carla)
        blueprints = world.get_blueprint_library()
        config = json.loads(Path('config.json').read_text())
        spawn_z = config.get('spawn_z_m', 1.5)
        if spawn_z not in (1.5, 1.8):
            raise ValueError('Unreviewed Native spawn-height candidate')
        ego = world.try_spawn_actor(blueprints.find('vehicle.tesla.model3'),
            carla.Transform(carla.Location(x=-35, y=-1.75, z=spawn_z), carla.Rotation(yaw=0)))
        other = world.try_spawn_actor(blueprints.find('vehicle.audi.tt'),
            carla.Transform(carla.Location(x=1.75, y=-35, z=spawn_z), carla.Rotation(yaw=90)))
        if ego is None or other is None:
            raise RuntimeError('Original actor spawn failed')
        owned.extend((ego, other))
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 85), ('sensor_tick', .05)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=pitch, yaw=90 if name == 'reference_corner' else 0)))
            owned.append(sensor)
            received = queue.Queue(); sensor.listen(received.put); queues[name] = received
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                '-s', f'{width}x{height}', '-r', '20', '-i', '-', '-frames:v',
                str(FRAMES), '-c:v', 'ffv1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        requests = [json.loads(line) for line in Path('request.jsonl').read_text().splitlines()]
        view_samples = []
        live_capture = PipelineCapture(client, ego, output, config['selected_case_id'],
                                       required_observations=('st.sight_distance', 'rel.visible'))
        with (output / 'native-motion.jsonl').open('x') as motion, \
                (output / 'interaction_history.jsonl').open('x') as interaction, \
                FrameMap(output / 'video_frames.jsonl') as frame_map:
            for index, request in enumerate(requests):
                target_speed = 0 if index and request['ego_center_xy_m'][0] == requests[index-1]['ego_center_xy_m'][0] else 4
                ego.set_target_velocity(carla.Vector3D(x=target_speed, y=0, z=0))
                other.set_target_velocity(carla.Vector3D(x=0, y=4 if index < 350 else 0, z=0))
                native_frame = world.tick()
                live_capture.capture(native_frame, index / 20)
                ego_source, other_source = actor_row(ego), actor_row(other)
                if index % 20 == 0 and ego_source['center_xyz_m'][0] < -6:
                    view_samples.append(view_sample(world, ego, other, carla, native_frame))
                heads = signal_readback(lights, carla)
                state = 'inoperative_dark'
                pose = {'native_frame': native_frame, 'video_frame': index, 'time_s': index / 20,
                    'ego_center_x_m': ego_source['center_xyz_m'][0],
                    'ego_front_x_m': max(vertex[0] for vertex in ego_source['body_xyz_m']),
                    'ego_speed_mps': ego_source['speed_mps'],
                    'ego': ego_source, 'other': other_source,
                    'signal_id': '701', 'signal_state': state,
                    'signal_readback': heads,
                    'source_kind': 'original_native', 'legal_verdict': None}
                motion.write(json.dumps(pose, allow_nan=False) + '\n')
                interaction.write(json.dumps({'frame': native_frame, 'time_s': index / 20,
                    'states': {'ego': {'body_vertices_m': ego_source['body_xyz_m']},
                               'other': {'body_vertices_m': other_source['body_xyz_m']}},
                    'source_kind': 'original_native'}, allow_nan=False) + '\n')
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
        live_capture.close()
        live_capture = None
        for name, process in encoders.items():
            process.stdin.close(); stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + stderr.decode()[-400:])
        (output / 'scene-survey.json').write_text(json.dumps({
            'source_kind': 'original_native', 'road_sha256': sha(source_road),
            'authored_geometry_inventory': authored,
            'stop_line_present': False, 'near_side_crosswalk_present': True, 'crosswalk_near_edge_x_m': -10.0,
            'sidewalk_derived_crosswalk_reviewed': False,
            'signal_installed': True, 'signal_uncovered': True,
            'official_device_provenance_reviewed': False,
            'through_highway_provenance_reviewed': False,
            'signal_id': '701',
            'ego_front_offset_m': None,
            'intersection_entry_front_x_m': -6.0,
            'driver_view_samples': view_samples,
            'review_pending': ['imported crosswalk pixels and sidewalk crossing',
                'official signal authority and uncovering',
                'through-highway legal designation',
                'continuous nearest point and driver perception']}, indent=2) + '\n')
        (output / 'signal_context.json').write_text(json.dumps({
            'intersection_polygon_xy_m': [[-6, -6], [6, -6], [6, 6], [-6, 6]],
            'source_kind': 'authored_OpenDRIVE_with_native_lane_readback',
            'legal_verdict_claimed': False}, indent=2) + '\n')
    except Exception as exc:
        (output / 'native-run-status.json').write_text(json.dumps({
            'errors': [str(exc)], 'frames_requested': FRAMES,
            'physical_acceptance_claimed': False}) + '\n')
        raise
    finally:
        if live_capture is not None:
            live_capture.close(confirmed=False)
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
            try:
                restoration = restore(client, saved)
            except Exception as exc:
                (output / 'native-run-status.json').write_text(json.dumps({
                    'errors': ['World restoration failed: ' + str(exc)],
                    'frames_requested': FRAMES,
                    'physical_acceptance_claimed': False}) + '\n')
                raise
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'physical_acceptance_claimed': False}) + '\n')
    seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                 encoder_exit_codes={name: 0 for name in queues}, context=authored)
    return {'frames': FRAMES, 'camera_names': list(queues),
            'source_review_complete': False, 'physical_acceptance_claimed': False}


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
