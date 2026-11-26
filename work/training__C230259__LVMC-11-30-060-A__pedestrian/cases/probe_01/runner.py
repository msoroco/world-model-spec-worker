"""Unselected outside-crosswalk Native request; --check is CPU-only."""
import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ASSIGNMENT = "training__C230259__LVMC-11-30-060-A__pedestrian"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
HERE = Path(__file__).resolve().parent


def request(index, case_id):
    if type(index) is not int or not 0 <= index < 600:
        raise ValueError("outside 600-frame contract")
    if case_id not in (ASSIGNMENT + "__probe_01", ASSIGNMENT + "__probe_02"):
        raise ValueError("unknown exact case")
    depart = 320 if case_id.endswith("probe_01") else 140
    return {"pedestrian_departure_frame": depart,
            "pedestrian_target_speed_mps": 1.2 if index >= depart else 0.0,
            "vehicle_target_speed_mps": 2.2,
            "vehicle_yield_command": None,
            "crossing_y_m": 10.0}


def post_tick_row(index, native_frame, elapsed_s, pedestrian, vehicles):
    if type(index) is not int or not 0 <= index < 600 or type(native_frame) is not int:
        raise ValueError("original frame identity required")
    if type(elapsed_s) not in (int, float) or not math.isfinite(elapsed_s):
        raise ValueError("original time required")
    pose = pedestrian.get_transform()
    points = sorted({(round(v.x, 5), round(v.y, 5))
                     for v in pedestrian.bounding_box.get_world_vertices(pose)})
    if len(points) != 4:
        raise ValueError("original pedestrian footprint required")
    observed = []
    for vehicle in vehicles:
        vpose, velocity = vehicle.get_transform(), vehicle.get_velocity()
        observed.append({"id": vehicle.id, "x_m": vpose.location.x,
                         "y_m": vpose.location.y,
                         "speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)})
    return {"native_frame": native_frame, "time_s": elapsed_s,
            "pedestrian_id": pedestrian.id, "pedestrian_footprint_xy_m": [list(v) for v in points],
            "vehicles": observed, "source": "native_post_tick"}


def check(config):
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-30-060-A", "C230259", "pedestrian"):
        raise ValueError("frozen identity differs")
    case = config.get("case_id")
    if case not in (ASSIGNMENT + "__probe_01", ASSIGNMENT + "__probe_02"):
        raise ValueError("exact case differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("30-second timing differs")
    if [c.get("name") for c in config.get("cameras", [])] != list(CAMERAS):
        raise ValueError("four-camera contract differs")
    root = ET.parse(HERE / "road.xodr").getroot()
    road = root.find("road")
    if road is None or road.get("junction") != "-1" or road.get("length") != "60":
        raise ValueError("authored road geometry differs")
    if root.findall(".//objects/object") or root.findall(".//junction"):
        raise ValueError("draft must omit marked crossing and intersection")
    assert request(0, case)["pedestrian_target_speed_mps"] == 0
    return {"passed": True, "case_id": case, "frames": 600, "rate_hz": 20,
            "cameras": list(CAMERAS), "native_capture_implemented": True,
            "source_meter_interface_implemented": True,
            "physical_crossing_observed": False, "legal_conclusion": None}




def survey(world, carla):
    """Fail before capture if Native road topology differs from crossing plan."""
    root = ET.fromstring(world.get_map().to_opendrive())
    roads = root.findall('road')
    if len(roads) != 1 or roads[0].get('id') != '1' or roads[0].get('junction') != '-1':
        raise RuntimeError('Native road/intersection survey differs')
    if root.findall('.//objects/object') or root.findall('.//junction'):
        raise RuntimeError('Native marked crossing or intersection appeared')
    sampled = []
    for y in (-20, 0, 10, 20):
        wp = world.get_map().get_waypoint(carla.Location(x=-1.75, y=y, z=1),
                                          project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != 1:
            raise RuntimeError(f'Native roadway lane survey differs at y={y}')
        pos = wp.transform.location
        if abs(pos.x + 1.75) > 1 or abs(pos.y-y) > 1:
            raise RuntimeError(f'Native roadway position survey differs at y={y}')
        sampled.append({'requested_y_m': y, 'native_xyz_m': [pos.x, pos.y, pos.z],
                        'road_id': wp.road_id, 'lane_id': wp.lane_id})
    return {'roadway_samples': sampled, 'marked_crosswalk_intervals_y_m': [],
            'intersection_intervals_y_m': [], 'physical_crosswalk_pixels_verified': False}


def execute(config, output_dir, host, port):
    import carla
    import queue
    import subprocess
    from worker_exchange.native_output import FrameMap, seal_capture
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    from crossing_meter import digest, measure
    check(config)
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
    owned, queues, encoders = [], {}, {}
    changed = False
    capture = None
    complete = False
    camera_plan = (
        ('overview', 1920, 1080, 0, -15, 18, -55),
        ('approach', 1280, 720, -7, 10, 6, -25),
        ('reference_corner', 1280, 720, -9, -12, 10, -35),
        ('driver_reference', 1280, 720, 8, 10, 8, -35),
    )
    try:
        world = client.generate_opendrive_world((HERE / 'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5, max_road_length=25,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        inspected = survey(world, carla)
        output.mkdir(parents=True)
        (output / 'acquisition-provenance.json').write_text(json.dumps({'provenance_kind': 'native', 'diagnostic_fixture': False}, indent=2) + '\n')
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        library = world.get_blueprint_library()
        walker_bp = sorted(library.filter('walker.pedestrian.*'), key=lambda b: b.id)[0]
        vehicle_bp = library.find('vehicle.tesla.model3')
        walker_bp.set_attribute('role_name', 'c230259_pedestrian_subject')
        vehicle_bp.set_attribute('role_name', 'c230259_roadway_vehicle')
        pedestrian = world.spawn_actor(walker_bp, carla.Transform(
            carla.Location(x=-5, y=10, z=1), carla.Rotation(yaw=0)))
        vehicle = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-1.75, y=-25, z=1), carla.Rotation(yaw=90)))
        owned.extend((pedestrian, vehicle))
        capture = PipelineCapture(client, pedestrian, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        for name, width, height, x, y, z, pitch in camera_plan:
            bp = library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', '.05')
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', '20', '-i', '-', '-frames:v', '600', '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'post-tick.jsonl').open('x') as trace, (output / 'trace.jsonl').open('x') as native_trace:
            first_time = None
            for index in range(600):
                motion = request(index, config['case_id'])
                pedestrian.apply_control(carla.WalkerControl(
                    direction=carla.Vector3D(x=1, y=0, z=0),
                    speed=motion['pedestrian_target_speed_mps']))
                vy = motion['vehicle_target_speed_mps'] if vehicle.get_transform().location.y < 25 else 0
                vehicle.set_target_velocity(carla.Vector3D(x=0, y=vy, z=0))
                frame = world.tick()
                stamp = world.get_snapshot()
                if stamp.frame != frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                if first_time is None:
                    first_time = stamp.timestamp.elapsed_seconds
                relative_time = stamp.timestamp.elapsed_seconds - first_time
                capture.capture(frame, relative_time)
                mapped = {}
                for name in queues:
                    image = queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera frame join failed: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(frame, relative_time, camera_native_frames=mapped)
                trace.write(json.dumps(post_tick_row(index, frame, relative_time,
                                                      pedestrian, [vehicle])) + '\n')
                pedestrian_pose = pedestrian.get_transform()
                pedestrian_velocity = pedestrian.get_velocity()
                native_trace.write(json.dumps({'frame': frame, 'time_s': relative_time,
                    'position': {'x': pedestrian_pose.location.x, 'y': pedestrian_pose.location.y, 'z': pedestrian_pose.location.z},
                    'position_m': [pedestrian_pose.location.x, pedestrian_pose.location.y, pedestrian_pose.location.z],
                    'heading_deg': pedestrian_pose.rotation.yaw,
                    'speed_mps': math.sqrt(pedestrian_velocity.x**2 + pedestrian_velocity.y**2 + pedestrian_velocity.z**2)}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + stderr.decode()[-400:])
        (output / 'crossing-context.json').write_text(json.dumps({
            'trace_sha256': digest(output / 'post-tick.jsonl'),
            'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'other_vehicle'},
            'source_kind': 'native_post_tick',
            'marked_crosswalk_intervals_y_m': inspected['marked_crosswalk_intervals_y_m'],
            'intersection_intervals_y_m': inspected['intersection_intervals_y_m'],
            'native_roadway_survey': inspected['roadway_samples'],
            'designated_place_prohibition': None,
            'pedestrian_id': pedestrian.id, 'vehicle_ids': [vehicle.id],
            'limitations': ['Section 11.30.070 designated-place applicability unresolved',
                            'Crosswalk pixels and actual precedence require review']}, indent=2) + '\n')
        measured = measure(output)
        complete = True
        (output / 'crossing-measurement.json').write_text(json.dumps(measured, indent=2) + '\n')
        return {'frames': 600, 'cameras': list(queues), 'measurement': measured,
                'physical_acceptance_claimed': False}
    finally:
        if capture is not None:
            capture.close(confirmed=complete)
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
        restoration = restore(client, saved) if changed else {'restored': True}
        if complete:
            seal_capture(output, frames=600, restoration=restoration, errors=[],
                         encoder_exit_codes={name: p.returncode for name,p in encoders.items()},
                         context={'case_id': config['case_id'], 'candidate_id': config.get('candidate_id', 'primary'), 'crosswalk_review': 'pending_original_source'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check == args.execute:
        raise SystemExit('choose --check or --execute')
    config = json.loads((HERE / 'config.json').read_text())
    if args.execute and not args.output_dir:
        raise SystemExit('--output-dir required for Native execution')
    print(json.dumps(check(config) if args.check else execute(config, args.output_dir, args.host, args.port), sort_keys=True))
