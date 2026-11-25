"""Original CARLA acquisition proposal for the slow extreme-left-lane pair.

The scripted actors make a reproducible encounter. Native readbacks, not requested
positions, are retained. Regulatory classification and driver notice require later
independent sources; this runner never assigns a legal verdict.
"""
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from geometry import check as geometry_check, open_drive

FRAMES = 600
RATE = 20
VIEWS = (('overview', 80, -30, 18), ('approach', 130, -13, 7),
         ('reference_corner', 220, -16, 8), ('driver_reference', 320, -12, 6))


def check():
    geometry = geometry_check()
    if FRAMES / RATE != 30 or len({view[0] for view in VIEWS}) != 4:
        raise ValueError('Capture profile differs')
    return {'frames': FRAMES, 'rate_hz': RATE, 'views': [view[0] for view in VIEWS],
            'geometry': geometry, 'native_executed': False,
            'physical_acceptance_claimed': False}


def planned_y(case, index):
    """Expected lane center for a lateral target-velocity phase; readback decides."""
    if case == 'reference' or index < 100:
        return -1.75
    if case != 'contrast':
        raise ValueError('Unknown exact case')
    if index >= 140:
        return -5.25
    return -1.75 - 3.5 * (index - 100) / 40


def _survey(mapping, carla):
    road = next((r for r in ET.fromstring(mapping.to_opendrive()).findall('road')
                 if r.attrib.get('id') == '1'), None)
    if road is None:
        raise RuntimeError('Native road readback absent')
    lanes = road.findall('lanes/laneSection/right/lane')
    if [(lane.attrib.get('id'), lane.attrib.get('type'),
         float(lane.find('width').attrib['a'])) for lane in lanes] != [
             ('-1', 'driving', 3.5), ('-2', 'driving', 3.5)]:
        raise RuntimeError('Native marked lane readback differs')
    samples = []
    for lane_id, y in ((-1, -1.75), (-2, -5.25)):
        waypoint = mapping.get_waypoint(carla.Location(x=100, y=y, z=1),
                                        project_to_road=True,
                                        lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != lane_id:
            raise RuntimeError('Native lane identity readback differs')
        samples.append({'lane_id': waypoint.lane_id, 'y_m': waypoint.transform.location.y})
    return {'format': 'c230259-left-lane-map-readback-v1',
            'same_direction_marked_lane_count': 2, 'extreme_left_lane_id': -1,
            'right_lane_id': -2, 'waypoints': samples,
            'opendrive_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()}


def _body(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    return [[point.x, point.y, point.z] for point in points]


def _write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def execute(case, output_dir, host='127.0.0.1', port=2000):
    import carla
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check()
    if case not in ('reference', 'contrast'):
        raise ValueError('Unknown exact case')
    output = Path(output_dir).resolve()
    if output.exists() and not (output / 'candidate-selection.json').is_file():
        raise ValueError('Use a materialized selected Native attempt directory')
    config = json.loads((output / 'config.json').read_text())
    rear_initial_x = float(config['rear_initial_x_m'])
    if rear_initial_x not in (-50.0, -55.0):
        raise ValueError('Unselected rear-spawn fallback')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    initial = client.get_world()
    if saved['settings'].synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for actor in initial.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, encoders, streams = [], {}, {}
    changed = False
    finished = False
    encoder_codes = {}
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=40, wall_height=0, additional_width=0,
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
        survey = _survey(world.get_map(), carla)
        blueprints = world.get_blueprint_library()
        model = blueprints.find('vehicle.tesla.model3')
        ego = world.spawn_actor(model, carla.Transform(carla.Location(x=20, y=-1.75, z=1)))
        rear = world.spawn_actor(model, carla.Transform(carla.Location(x=rear_initial_x, y=-1.75, z=1)))
        owned.extend((ego, rear))
        if ego.type_id != 'vehicle.tesla.model3' or rear.type_id != 'vehicle.tesla.model3':
            raise RuntimeError('Native actor readback differs')
        output.mkdir(parents=True, exist_ok=True)
        capture = output / 'capture'
        graph_dir = capture / 'native' / 'graphs' / 'base'
        graph_dir.mkdir(parents=True, exist_ok=True)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        _write(output / 'native-map-readback.json', survey)
        _write(output / 'native-road-context.json', {
            'source_kind': 'original_native', 'capture_hz': RATE, 'frames': FRAMES,
            'same_direction_marked_lane_count': 2, 'extreme_left_lane_id': -1,
            'right_lane_id': -2, 'posted_speed_limit_mps': 25.0,
            'posted_speed_limit_mps_source': 'authored_target_only',
            'controlled_access_original_verified': False,
            'posted_limit_original_verified': False,
            'driver_notice_original_verified': False,
            'subsection_2_exception_review': None})
        _write(output / 'context.json', {
            'law_id': 'NRS-484B-208-1', 'cell_id': 'C230259',
            'source_kind': 'original_native', 'city_or_town_geography_verified': False,
            'hov_lane_present': False, 'left_turn_requested': False,
            'subject_overtaking_other_vehicle_requested': False,
            'official_control_reviewed': False,
            'emergency_authorization_reviewed': False,
            'maintenance_or_emergency_duty_verified': False,
            'weather': 'clear', 'legal_verdict': None})
        for name, x, y, z in VIEWS:
            bp = blueprints.find('sensor.camera.rgb')
            width, height = (1920, 1080) if name == 'overview' else (1280, 720)
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=-20)))
            owned.append(camera)
            stream = queue.Queue()
            camera.listen(stream.put)
            streams[name] = stream
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', str(RATE), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (
                output / 'native-actors.jsonl').open('x') as actors, (
                output / 'trace.jsonl').open('x') as trace, (
                capture / 'evidence.jsonl').open('x') as evidence, (
                capture / 'native' / 'frames.jsonl').open('x') as graphs:
            first_time = None
            for index in range(FRAMES):
                lateral = -1.75 if case == 'contrast' and 100 <= index < 140 else 0
                ego.set_target_velocity(carla.Vector3D(x=20, y=lateral, z=0))
                rear.set_target_velocity(carla.Vector3D(x=27, y=0, z=0))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot identity differs')
                if first_time is None:
                    first_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - first_time
                camera_frames, camera_hashes = {}, {}
                for name, _, _, _ in VIEWS:
                    image = streams[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = streams[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera/Native frame join differs: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                    camera_hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                frame_map.append(native_frame, time_s,
                                 camera_native_frames=camera_frames,
                                 source_rgb_sha256=camera_hashes)
                ego_pose, rear_pose = ego.get_transform().location, rear.get_transform().location
                ego_velocity, rear_velocity = ego.get_velocity(), rear.get_velocity()
                ego_speed = (ego_velocity.x**2 + ego_velocity.y**2 + ego_velocity.z**2)**.5
                rear_speed = (rear_velocity.x**2 + rear_velocity.y**2 + rear_velocity.z**2)**.5
                ego_lane = world.get_map().get_waypoint(ego_pose, project_to_road=True,
                    lane_type=carla.LaneType.Driving).lane_id
                rear_lane = world.get_map().get_waypoint(rear_pose, project_to_road=True,
                    lane_type=carla.LaneType.Driving).lane_id
                row = {'frame': index, 'native_frame': native_frame, 'time_s': time_s,
                       'source_kind': 'original_native',
                       'ego_longitudinal_m': ego_pose.x,
                       'rear_longitudinal_m': rear_pose.x,
                       'ego_speed_mps': ego_speed, 'rear_speed_mps': rear_speed,
                       'speed_method': 'original_trace_actor_get_velocity',
                       'ego_lane_id': ego_lane, 'rear_lane_id': rear_lane,
                       'ego_body_vertices_m': _body(ego),
                       'rear_body_vertices_m': _body(rear)}
                actors.write(json.dumps(row) + '\n')
                trace.write(json.dumps({
                    'frame': native_frame, 'time_s': time_s,
                    'position': {'x': ego_pose.x, 'y': ego_pose.y, 'z': ego_pose.z},
                    'position_m': [ego_pose.x, ego_pose.y, ego_pose.z],
                    'heading_deg': ego.get_transform().rotation.yaw,
                    'speed_mps': ego_speed, 'speed_mph': ego_speed / .44704,
                    'velocity_mps': [ego_velocity.x, ego_velocity.y, ego_velocity.z],
                    'control': {'throttle': 0, 'steer': 0, 'brake': 0,
                                'hand_brake': False}}) + '\n')
                evidence.write(json.dumps({
                    'original_frame': native_frame, 'replay_frame': native_frame,
                    'recording_time_s': time_s, 'replay_simulation_time_s': time_s,
                    'actor_id': ego.id,
                    'ego': {'position_m': [ego_pose.x, ego_pose.y, ego_pose.z],
                            'heading_deg': ego.get_transform().rotation.yaw,
                            'speed_mps': ego_speed, 'body_vertices_m': _body(ego),
                            'speed_provenance': 'original_trace_actor_get_velocity'},
                    'world': {'road_projection': {'road_id': 1,
                              'lane_id': ego_lane, 's_m': ego_pose.x + 100}}}) + '\n')
                graph = f'graphs/base/{native_frame:08d}.adapter.json'
                (graph_dir / f'{native_frame:08d}.adapter.json').write_text(json.dumps({
                    'attributes': {'frame': native_frame}, 'nodes': [], 'edges': []}) + '\n')
                graphs.write(json.dumps({'abstract': graph, 'adapter_graph': graph,
                    'base': graph, 'edges': 0, 'frame': native_frame,
                    'nodes': 0, 'simulation_time': time_s, 'time_s': time_s}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            if encoder_codes[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed ' + name + ': ' + error.decode()[-400:])
        from left_lane_measure import sha
        _write(capture / 'manifest.json', {'frames': FRAMES,
            'extraction_confirmed': True, 'synthetic_diagnostic': False,
            'sources': {'road.xodr': sha(output / 'road.xodr'),
                        'trace.jsonl': sha(output / 'trace.jsonl')},
            'required_observations': []})
        (capture / 'recorder_info.txt').write_text(
            f'Original scripted CARLA actor readback and synchronized RGB capture.\nCreate {ego.id}: {ego.type_id} (0)\n')
        _write(output / 'source-hashes.json', {
            name: sha(output / name) for name in
            ('native-actors.jsonl', 'native-road-context.json')})
        finished = True
        return {'case': case, 'frames': FRAMES,
                'native_sources_written': True, 'physical_acceptance_claimed': False}
    except Exception as exc:
        if output.exists():
            _write(output / 'native-run-status.json', {
                'errors': [str(exc)], 'native_capture_completed': False})
        raise
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
            restoration = restore(client, saved)
            if finished:
                _write(output / 'native-capture-report.json', {
                    'case': case, 'frames': FRAMES,
                    'encoder_exit_codes': encoder_codes,
                    'restoration': restoration,
                    'physical_acceptance_claimed': False})
                _write(output / 'acquisition-provenance.json', {
                    'provenance_kind': 'native', 'diagnostic_fixture': False})
                seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                             encoder_exit_codes=encoder_codes,
                             context={'case': case, 'law_id': 'NRS-484B-208-1'})
