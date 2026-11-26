"""Survey-gated original Native bicycle capture for signed roadway restriction."""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from geometry import check as geometry_check, open_drive, SIGN_NAME

FRAMES = 600
RATE = 20
CAMERAS = (
    ('overview', 1920, 1080, 0, -18, 16, -40),
    ('approach', 1280, 720, -55, -10, 7, -18),
    ('reference_corner', 1280, 720, -55, -8, 5, -10),
    ('driver_reference', 1280, 720, 20, -12, 10, -30),
)
CASES = {'probe_01': {'surface': 'shoulder', 'y_m': -4.75},
         'probe_02': {'surface': 'roadway', 'y_m': -1.75}}


def check(case_id=None):
    g = geometry_check()
    if case_id is not None and case_id.rsplit('__', 1)[-1] not in CASES:
        raise ValueError('unknown exact signed-roadway case')
    if FRAMES / RATE != 30 or len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('four cameras and 30-second capture required')
    return {'passed': True, 'geometry': g, 'frames': FRAMES, 'rate_hz': RATE,
            'case_variants': CASES,
            'cameras': [c[0] for c in CAMERAS], 'native_imported': False,
            'physical_acceptance_claimed': False}


def survey(world, carla):
    mapping = world.get_map()
    root = ET.fromstring(mapping.to_opendrive())
    signals = [s for s in root.findall('.//signal') if s.attrib.get('id') == '100']
    if len(signals) != 1 or signals[0].attrib.get('name') != SIGN_NAME or signals[0].attrib.get('orientation') != '+':
        raise RuntimeError('Native signed bicycle restriction readback failed')
    lane_rows = []
    for x in (-40, 0, 40):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1:
            raise RuntimeError(f'Native governed roadway readback failed at x={x}')
        position = wp.transform.location
        if abs(position.x-x) > 1 or abs(position.y+1.75) > 1:
            raise RuntimeError(f'Native governed roadway position readback failed at x={x}')
        lane_rows.append({'requested_x_m': x, 'native_xyz_m': [position.x, position.y, position.z],
                          'road_id': wp.road_id, 'lane_id': wp.lane_id})
    shoulder_rows = []
    for x in (-40, 0, 40):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-4.75, z=1),
                                  project_to_road=False, lane_type=carla.LaneType.Shoulder)
        if wp is None or wp.road_id != 1 or wp.lane_id != -2:
            raise RuntimeError(f'Native off-road shoulder readback failed at x={x}')
        position = wp.transform.location
        if abs(position.x-x) > 1 or abs(position.y+4.75) > 1.25:
            raise RuntimeError(f'Native off-road shoulder position readback failed at x={x}')
        shoulder_rows.append({'requested_x_m': x, 'native_xyz_m': [position.x, position.y, position.z],
                              'road_id': wp.road_id, 'lane_id': wp.lane_id})
    return {'sign': dict(signals[0].attrib), 'roadway': lane_rows,
            'shoulder': shoulder_rows,
            'sign_pixels_confirmed': False, 'city_designation_confirmed': False}


def execute(output_dir, host, port, case_id):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    check(case_id)
    variant = CASES[case_id.rsplit('__', 1)[-1]]
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
        output.mkdir(parents=True)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        blueprints = world.get_blueprint_library()
        bicycle_bp = blueprints.find('vehicle.bh.crossbike')
        bicycle_bp.set_attribute('role_name', 'c230207_human_bicycle_subject')
        bicycle = world.spawn_actor(bicycle_bp, carla.Transform(
            carla.Location(x=-50, y=variant['y_m'], z=1), carla.Rotation(yaw=0)))
        if bicycle is None:
            raise RuntimeError('Original bicycle spawn failed')
        owned.append(bicycle)
        (output / 'restriction-context.json').write_text(json.dumps({
            'case_id': case_id, 'target_surface': variant['surface'],
            'rider_class': 'human_propelled_bicycle', 'blueprint_id': bicycle.type_id,
            'wheel_characteristics_reviewed': False,
            'sign_id': '100', 'sign_text': SIGN_NAME, 'sign_x_m': -45,
            'sign_orientation': 'positive_s',
            'native_sign_survey': readback['sign'], 'native_roadway_survey': readback['roadway'],
            'native_shoulder_survey': readback['shoulder'],
            'roadway_xy_m': [[-60, -3.5], [60, -3.5], [60, 0], [-60, 0]],
            'city_traffic_engineer_designation_verified': False,
            'physical_sign_pixels_verified': False}, indent=2) + '\n')
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
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'bicycle-poses.jsonl').open('x') as poses:
            first_elapsed = None
            for index in range(FRAMES):
                bicycle.set_target_velocity(carla.Vector3D(x=2.3, y=0, z=0))
                native_frame = world.tick()
                native_snapshot = world.get_snapshot()
                if native_snapshot.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                absolute_time = native_snapshot.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = absolute_time
                relative_time = absolute_time - first_elapsed
                transform = bicycle.get_transform()
                velocity = bicycle.get_velocity()
                mapped = {}
                for name in queues:
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError(f'Original camera frame join failed: {name}')
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, relative_time, camera_native_frames=mapped)
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': relative_time, 'native_elapsed_seconds': absolute_time,
                    'rider_xy_m': [transform.location.x, transform.location.y],
                    'rider_z_m': transform.location.z,
                    'velocity_xy_mps': [velocity.x, velocity.y],
                    'rider_actor_id': bicycle.id, 'rider_blueprint_id': bicycle.type_id}) + '\n')
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
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--output-dir')
    p.add_argument('--case')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=2000)
    a = p.parse_args()
    if a.check == a.execute:
        raise SystemExit('choose --check or --execute')
    if a.execute and (not a.output_dir or not a.case):
        raise SystemExit('--output-dir and --case required for Native execution')
    print(json.dumps(check(a.case) if a.check else execute(a.output_dir, a.host, a.port, a.case)))
