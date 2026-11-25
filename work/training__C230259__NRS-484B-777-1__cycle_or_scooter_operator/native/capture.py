"""Original Native capture proposal for C230259 reference/contrast bicycle paths.

CPU check validates the authored construction. Capture requires a supplied exclusive
CARLA endpoint and records original readbacks; it never judges legal compliance.
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
CASES = {'reference': -2.65, 'contrast': -1.45}
CAMERAS = (('overview', -5, -16, 15, -45), ('approach', 15, -8, 6, -20),
           ('reference_corner', 55, -12, 7, -25),
           ('driver_reference', 85, -8, 6, -20))


def check():
    geometry = geometry_check()
    if FRAMES / RATE != 30 or len(CAMERAS) != 4 or len({x[0] for x in CAMERAS}) != 4:
        raise ValueError('Capture duration or four camera views differ')
    if CASES['reference'] == CASES['contrast']:
        raise ValueError('Controlled lateral settings coincide')
    return {'passed': True, 'cases': CASES, 'frames': FRAMES, 'rate_hz': RATE,
            'views': [x[0] for x in CAMERAS], 'geometry': geometry,
            'native_executed': False, 'physical_acceptance_claimed': False}


def _body(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    xs, ys = [p.x for p in points], [p.y for p in points]
    return [[min(xs), min(ys)], [max(xs), min(ys)],
            [max(xs), max(ys)], [min(xs), max(ys)]]


def _survey(mapping, carla):
    root = ET.fromstring(mapping.to_opendrive())
    road = next((r for r in root.findall('road') if r.attrib.get('id') == '1'), None)
    if road is None:
        raise RuntimeError('Native road 1 readback absent')
    lanes = road.findall('lanes/laneSection/right/lane')
    if [(x.attrib.get('id'), x.attrib.get('type'),
         float(x.find('width').attrib['a'])) for x in lanes] != [
             ('-1', 'driving', 3.5), ('-2', 'shoulder', 2.5)]:
        raise RuntimeError('Native lane/shoulder width readback differs')
    samples = []
    for x in (0, 30, 60, 90):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1 or abs(wp.transform.location.y + 1.75) > .3:
            raise RuntimeError('Native roadway lane readback differs')
        samples.append({'x_m': x, 'waypoint_y_m': wp.transform.location.y,
                        'road_id': wp.road_id, 'lane_id': wp.lane_id})
    return {'format': 'c230259-road-edge-v1', 'right_edge_source': 'native_map_readback',
            'right_side': 'lower_y', 'right_roadway_edge_y_m': -3.5,
            'road_id': 1, 'driving_lane_id': -1, 'shoulder_lane_id': -2,
            'native_waypoint_samples': samples,
            'readback_opendrive_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()}


def execute(case, output_dir, host='127.0.0.1', port=2000, requested_y=None):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    check()
    if case not in CASES:
        raise ValueError('Unknown exact case setting')
    cycle_y = CASES[case] if requested_y is None else float(requested_y)
    if abs(cycle_y - CASES[case]) > .16:
        raise ValueError('Candidate bicycle offset outside predeclared physical-risk fallback')
    output = Path(output_dir).resolve()
    if output.exists():
        raise ValueError('Use a fresh original Native attempt directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    initial = client.get_world()
    if saved['settings'].synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for actor in initial.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, encoders, camera_queues = [], {}, {}
    changed = False
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
        bp = world.get_blueprint_library()
        cycle_bp = bp.find('vehicle.bh.crossbike')
        vehicle_bp = bp.find('vehicle.tesla.model3')
        cycle_bp.set_attribute('role_name', 'c230259_bicycle_subject')
        vehicle_bp.set_attribute('role_name', 'c230259_standing_vehicle')
        cycle = world.spawn_actor(cycle_bp, carla.Transform(
            carla.Location(x=10, y=cycle_y, z=1), carla.Rotation(yaw=0)))
        standing = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=55, y=-5, z=1), carla.Rotation(yaw=0)))
        owned.extend((cycle, standing))
        if cycle.type_id != 'vehicle.bh.crossbike' or standing.type_id != 'vehicle.tesla.model3':
            raise RuntimeError('Native actor blueprints differ')
        standing.set_simulate_physics(False)
        output.mkdir(parents=True)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'native-map-readback.json').write_text(json.dumps(survey, indent=2) + '\n')
        (output / 'standing-vehicle.json').write_text(json.dumps({
            'format': 'c230259-standing-vehicle-v1', 'source_kind': 'native_actor',
            'actor_id': standing.id, 'blueprint': standing.type_id,
            'body_native_xy_m': _body(standing), 'physics_disabled_for_stationary_role': True},
            indent=2) + '\n')
        for name, x, y, z, pitch in CAMERAS:
            camera_bp = bp.find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', '1920' if name == 'overview' else '1280')
            camera_bp.set_attribute('image_size_y', '1080' if name == 'overview' else '720')
            camera_bp.set_attribute('fov', '85')
            camera_bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            stream = queue.Queue()
            camera.listen(stream.put)
            camera_queues[name] = stream
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                '1920x1080' if name == 'overview' else '1280x720', '-r', str(RATE),
                '-i', '-', '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (
                output / 'native-cycle-frames.jsonl').open('x') as trace:
            first_time = None
            for index in range(FRAMES):
                cycle.set_target_velocity(carla.Vector3D(x=3, y=0, z=0))
                native_frame = world.tick()
                snapshot_now = world.get_snapshot()
                if snapshot_now.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot mismatch')
                elapsed = snapshot_now.timestamp.elapsed_seconds
                if first_time is None:
                    first_time = elapsed
                time_s = elapsed - first_time
                frame_hashes = {}
                camera_frames = {}
                for name, _, _, _, _ in CAMERAS:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera frame join differs: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    frame_hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s,
                                 camera_native_frames=camera_frames,
                                 source_rgb_sha256=frame_hashes)
                row = {'frame': index, 'native_frame': native_frame, 'time_s': time_s,
                       'source_kind': 'native_actor', 'actor_id': cycle.id,
                       'blueprint': cycle.type_id, 'body_native_xy_m': _body(cycle),
                       'standing_body_native_xy_m': _body(standing)}
                trace.write(json.dumps(row) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            errors = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed ' + name + ': ' + errors.decode()[-400:])
        from measure_right_edge import SOURCES, digest
        (output / 'source-hashes.json').write_text(json.dumps(
            {name: digest(output / name) for name in SOURCES}, indent=2) + '\n')
        return {'case': case, 'frames': FRAMES, 'native_sources_written': True,
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
