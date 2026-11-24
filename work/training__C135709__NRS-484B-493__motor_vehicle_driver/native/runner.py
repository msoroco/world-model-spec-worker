"""Paired one-way curb parking Native draft; no physical or legal result claimed."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from geometry import SIGN_NAME, check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = (
    ('overview', 1280, 720, 0, -18, 16, -40),
    ('sign_approach', 1280, 720, -15, -12, 7, -18),
    ('sign_face', 1280, 720, -42, 7, 5, -8),
    ('parking_side', 1280, 720, 22, -14, 9, -30),
)


def check():
    geometry = geometry_check()
    if FRAMES / RATE != 30 or len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('four cameras and 30-second capture required')
    return {'passed': True, 'geometry': geometry, 'frames': FRAMES,
            'rate_hz': RATE, 'camera_names': [c[0] for c in CAMERAS],
            'physical_acceptance_claimed': False}


def survey(world, carla):
    mapping = world.get_map()
    root = ET.fromstring(mapping.to_opendrive())
    signals = [s for s in root.findall('.//signal') if s.attrib.get('id') == '493']
    if len(signals) != 1 or signals[0].attrib.get('name') != SIGN_NAME or signals[0].attrib.get('orientation') != '+':
        raise RuntimeError('Native left-side parking notice readback failed')
    rows = []
    for name, y, lane_id, lane_type in (
            ('left_shoulder', 1.5, 1, carla.LaneType.Shoulder),
            ('driving', -1.75, -1, carla.LaneType.Driving),
            ('right_shoulder', -5.0, -2, carla.LaneType.Shoulder)):
        waypoint = mapping.get_waypoint(carla.Location(x=20, y=y, z=1),
                                        project_to_road=True, lane_type=lane_type)
        if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != lane_id:
            raise RuntimeError('Native curb-side lane readback failed: ' + name)
        rows.append({'name': name, 'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                     'native_xy_m': [waypoint.transform.location.x, waypoint.transform.location.y]})
    return {'sign': dict(signals[0].attrib), 'lanes': rows,
            'one_way_legal_designation_verified': False, 'official_authority_verified': False,
            'physical_sign_pixels_verified': False}


def execute(output_dir, side, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    check()
    if side not in ('left', 'right'):
        raise ValueError('side must be left or right')
    output = Path(output_dir).resolve()
    if (output / 'road.xodr').exists() or (output / 'vehicle-pose.jsonl').exists():
        raise ValueError('choose a fresh original Native attempt directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('requires an exclusive idle asynchronous Native world')
    owned, encoders, queues = [], {}, {}
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
        output.mkdir(parents=True, exist_ok=True)
        source_map = world.get_map().to_opendrive().encode()
        (output / 'road.xodr').write_bytes(source_map)
        (output / 'road-context.json').write_text(json.dumps({
            'assignment_id': 'training__C135709__NRS-484B-493__motor_vehicle_driver',
            'source_kind': 'native_saved_sample', 'road_id': '1',
            'map_source_sha256': hashlib.sha256(source_map).hexdigest(),
            'one_way_designation_source_sha256': None,
            'street_boundary_source_sha256': hashlib.sha256(source_map).hexdigest(),
            'device_authority_source_sha256': None,
            'device_content_source_sha256': hashlib.sha256(source_map).hexdigest(),
            'device_erection_source_sha256': None,
            'roadway_is_one_way': None, 'device_id': '493', 'device_erected': None,
            'device_official': None, 'notice_prohibits_left_standing_or_parking': None,
            'device_governs_road_id': '1', 'centerline_origin_xy_m': [0, 0],
            'permitted_direction_xy': [1, 0], 'governed_longitudinal_extent_m': [0, 30],
            'street_half_width_m': 6.5, 'native_survey': readback,
            'physical_sign_pixels_verified': False,
            'operator_source_review_required': True}, indent=2) + '\n')
        blueprints = world.get_blueprint_library()
        vehicle_bp = blueprints.find('vehicle.tesla.model3')
        vehicle_bp.set_attribute('role_name', 'c135709_parking_subject')
        target_y = 1.5 if side == 'left' else -5.0
        vehicle = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-30, y=target_y, z=1), carla.Rotation(yaw=0)))
        owned.append(vehicle)
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
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', str(RATE), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'vehicle-pose.jsonl').open('x') as poses:
            first_elapsed = None
            for index in range(FRAMES):
                # Engineering parking controller; stop timing and actual footprint are measured later.
                vehicle.apply_control(carla.VehicleControl(throttle=.18 if index < 210 else 0,
                                                           brake=0 if index < 210 else 1,
                                                           hand_brake=index >= 300))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                absolute = snap.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = absolute
                relative = absolute - first_elapsed
                transform, velocity = vehicle.get_transform(), vehicle.get_velocity()
                extent = vehicle.bounding_box.extent
                x, y = transform.location.x, transform.location.y
                yaw = math.radians(transform.rotation.yaw)
                co, si = math.cos(yaw), math.sin(yaw)
                corners = [[x + dx*co - dy*si, y + dx*si + dy*co]
                           for dx, dy in ((-extent.x, -extent.y), (extent.x, -extent.y),
                                          (extent.x, extent.y), (-extent.x, extent.y))]
                mapped = {}
                for name in queues:
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera frame join failed: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, relative, camera_native_frames=mapped)
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': relative, 'native_elapsed_seconds': absolute,
                    'vehicle_id': str(vehicle.id), 'vehicle_blueprint_id': vehicle.type_id,
                    'speed_mps': velocity.length(), 'yaw_deg': transform.rotation.yaw,
                    'footprint_corners_xy_m': corners, 'camera_native_frames': mapped}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + stderr.decode()[-400:])
        return {'frames': FRAMES, 'side': side, 'native_survey': readback,
                'source_review_required': True, 'physical_acceptance_claimed': False}
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
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--output-dir')
    p.add_argument('--side', choices=('left', 'right'))
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=2000)
    a = p.parse_args()
    if a.check and (a.execute or a.output_dir):
        raise SystemExit('--check cannot create a Native attempt')
    if a.check:
        print(json.dumps(check()))
    else:
        if not a.output_dir:
            raise SystemExit('--output-dir required for Native execution')
        side = a.side or json.loads((Path(__file__).parent / 'config.json').read_text())['parking_side']
        print(json.dumps(execute(a.output_dir, side, a.host, a.port)))
