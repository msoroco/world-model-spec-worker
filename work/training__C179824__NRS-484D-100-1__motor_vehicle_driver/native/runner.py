"""Original Native lamp-control draft; official and pixel facts remain unverified."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from geometry import SIGN_NAME, check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = (
    ('overview', 1280, 720, 0, -20, 16, -38),
    ('device_approach', 1280, 720, -52, -13, 7, -16),
    ('device_face', 1280, 720, -55, -8, 5, -10),
    ('vehicle_lamps', 1280, 720, 5, 8, 5, -8),
)


def check():
    geometry = geometry_check()
    if FRAMES / RATE != 30 or len(CAMERAS) != 4 or len({x[0] for x in CAMERAS}) != 4:
        raise ValueError('four cameras and 30-second capture required')
    return {'passed': True, 'geometry': geometry, 'frames': FRAMES,
            'rate_hz': RATE, 'camera_names': [x[0] for x in CAMERAS],
            'original_pixels_verified': False, 'physical_acceptance_claimed': False}


def survey(world, carla):
    mapping = world.get_map()
    root = ET.fromstring(mapping.to_opendrive())
    signs = [s for s in root.findall('.//signal') if s.attrib.get('id') == '100']
    if len(signs) != 1 or signs[0].attrib.get('name') != SIGN_NAME or signs[0].attrib.get('orientation') != '+':
        raise RuntimeError('Native lamp-use instruction readback failed')
    lanes = []
    for x in (-60, -20, 20):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1:
            raise RuntimeError('Native paved roadway readback failed')
        lanes.append({'requested_x_m': x, 'road_id': wp.road_id, 'lane_id': wp.lane_id,
                      'native_xy_m': [wp.transform.location.x, wp.transform.location.y]})
    return {'sign': dict(signs[0].attrib), 'roadway': lanes,
            'official_authority_verified': False, 'physical_sign_pixels_verified': False,
            'highway_dedication_verified': False}


def execute(output_dir, lamp_setting_on, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    check()
    output = Path(output_dir).resolve()
    if (output/'road.xodr').exists() or (output/'vehicle-lamps.jsonl').exists():
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
        settings.fixed_delta_seconds = 1/RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        readback = survey(world, carla)
        output.mkdir(parents=True, exist_ok=True)
        source_map = world.get_map().to_opendrive().encode()
        (output/'road.xodr').write_bytes(source_map)
        (output/'lamp-context.json').write_text(json.dumps({
            'assignment_id': 'training__C179824__NRS-484D-100-1__motor_vehicle_driver',
            'source_kind': 'native_saved_sample', 'road_id': '1',
            'map_source_sha256': hashlib.sha256(source_map).hexdigest(),
            'highway_source_sha256': None, 'vehicle_class_source_sha256': None,
            'device_content_source_sha256': hashlib.sha256(source_map).hexdigest(),
            'device_authority_source_sha256': None,
            'device_placement_source_sha256': hashlib.sha256(source_map).hexdigest(),
            'device_timing_source_sha256': None,
            'state': 'Nevada', 'public_highway': None,
            'vehicle_class': None, 'directive': 'use_lamps', 'device_official': None,
            'device_governs_road_id': '1', 'native_survey': readback,
            'daylight_weather_request': 'ClearNoon',
            'civil_time_sunset_sunrise_verified': False,
            '1000_ft_discernibility_verified': False,
            'parked_exception_resolved': False,
            'actual_lamp_pixels_verified': False}, indent=2) + '\n')
        blueprints = world.get_blueprint_library()
        vehicle_bp = blueprints.find('vehicle.tesla.model3')
        vehicle_bp.set_attribute('role_name', 'c179824_lamp_subject')
        vehicle = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-70, y=-1.75, z=1), carla.Rotation(yaw=0)))
        owned.append(vehicle)
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', str(1/RATE))
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
                '-c:v', 'ffv1', '-level', '1', str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output/'video_frames.jsonl') as frame_map, (output/'vehicle-lamps.jsonl').open('x') as trace:
            first_elapsed = None
            for index in range(FRAMES):
                requested = (carla.VehicleLightState.Position | carla.VehicleLightState.LowBeam
                             if lamp_setting_on else carla.VehicleLightState(0))
                vehicle.set_light_state(carla.VehicleLightState(requested))
                vehicle.set_target_velocity(carla.Vector3D(x=3, y=0, z=0))
                native_frame = world.tick()
                snapshot_now = world.get_snapshot()
                if snapshot_now.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                absolute = snapshot_now.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = absolute
                relative = absolute-first_elapsed
                transform, velocity = vehicle.get_transform(), vehicle.get_velocity()
                native_lamps = int(vehicle.get_light_state())
                mapped = {}
                for name in queues:
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera frame join failed: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, relative, camera_native_frames=mapped)
                trace.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': relative, 'native_elapsed_seconds': absolute,
                    'vehicle_id': str(vehicle.id), 'vehicle_blueprint_id': vehicle.type_id,
                    'road_id': '1', 'vehicle_xy_m': [transform.location.x, transform.location.y],
                    'speed_mps': velocity.length(), 'device_active': transform.location.x >= -55,
                    'headlamp_setting_on': bool(native_lamps & int(carla.VehicleLightState.LowBeam)),
                    'position_lamp_setting_on': bool(native_lamps & int(carla.VehicleLightState.Position)),
                    'native_light_state_bits': native_lamps,
                    'camera_native_frames': mapped})+'\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: '+name+': '+stderr.decode()[-400:])
        return {'frames': FRAMES, 'lamp_setting_on': lamp_setting_on,
                'native_survey': readback, 'source_review_required': True,
                'physical_acceptance_claimed': False}
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restore(client, saved)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--output-dir')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=2000)
    a = p.parse_args()
    if a.check:
        if a.output_dir:
            raise SystemExit('--check cannot create a Native attempt')
        print(json.dumps(check()))
    else:
        if not a.output_dir:
            raise SystemExit('--output-dir required for Native execution')
        lamp_on = json.loads((Path(__file__).parent/'config.json').read_text())['lamp_setting_on']
        print(json.dumps(execute(a.output_dir, lamp_on, a.host, a.port)))
