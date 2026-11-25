"""Original Native acquisition draft for the 1,000-foot discernibility branch.

The trace records geometry and camera frames. A separate source review must
decide whether the person and vehicle are clearly discernible in those frames.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess

from visibility_geometry import (EGO_REFERENCE_X_M, STATUTORY_DISTANCE_M,
                                 TARGET_REFERENCE_X_M, check as geometry_check,
                                 open_drive)


FRAMES = 600
RATE_HZ = 20
CAMERAS = (
    ('overview', 1920, 1080, -40, -60, 50, -30),
    ('approach', 1280, 720, EGO_REFERENCE_X_M + 15, -18, 10, -8),
    ('reference_corner', 1280, 720, TARGET_REFERENCE_X_M - 20, -16, 8, -8),
    ('driver_reference', 1280, 720, 1, 0, 1.5, 0),
)


def check():
    geometry = geometry_check()
    if FRAMES / RATE_HZ != 30 or len(CAMERAS) != 4:
        raise ValueError('30-second four-view acquisition required')
    if [c[0] for c in CAMERAS] != ['overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('capture camera profile changed')
    if TARGET_REFERENCE_X_M - EGO_REFERENCE_X_M != STATUTORY_DISTANCE_M:
        raise ValueError('1,000-foot reference changed')
    return {'passed': True, 'geometry': geometry, 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'camera_names': [c[0] for c in CAMERAS],
            'person_and_vehicle_pixels_verified': False,
            'physical_acceptance_claimed': False}


def execute(output_dir: str, host: str, port: int, weather_name: str):
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
        settings.fixed_delta_seconds = 1/RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        weather = getattr(carla.WeatherParameters, weather_name)
        world.set_weather(weather)
        mapping = world.get_map()
        for x in (EGO_REFERENCE_X_M, TARGET_REFERENCE_X_M):
            waypoint = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1),
                                            project_to_road=True,
                                            lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != -1:
                raise RuntimeError('Native roadway reference readback failed')
        output.mkdir(parents=True)
        source_map = mapping.to_opendrive().encode()
        (output/'road.xodr').write_bytes(source_map)
        (output/'visibility-context.json').write_text(json.dumps({
            'assignment_id': 'training__C179824__NRS-484D-100-1__motor_vehicle_driver',
            'source_kind': 'native_saved_sample',
            'map_source_sha256': hashlib.sha256(source_map).hexdigest(),
            'reference_distance_m': STATUTORY_DISTANCE_M,
            'weather_request': weather_name,
            'person_pixels_reviewed': False,
            'vehicle_pixels_reviewed': False,
            'civil_time_verified': False,
            'highway_dedication_verified': False,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        blueprints = world.get_blueprint_library()
        vehicle_bp = blueprints.find('vehicle.tesla.model3')
        vehicle_bp.set_attribute('role_name', 'c179824_visibility_subject')
        ego = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=EGO_REFERENCE_X_M, y=-1.75, z=1)))
        owned.append(ego)
        target_bp = blueprints.find('vehicle.audi.a2')
        target_bp.set_attribute('role_name', 'c179824_visibility_target')
        target = world.spawn_actor(target_bp, carla.Transform(
            carla.Location(x=TARGET_REFERENCE_X_M, y=-1.75, z=1)))
        owned.append(target)
        walker_bp = blueprints.filter('walker.pedestrian.*')[0]
        person = world.spawn_actor(walker_bp, carla.Transform(
            carla.Location(x=TARGET_REFERENCE_X_M, y=-5.0, z=1)))
        owned.append(person)
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', str(1/RATE_HZ))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)),
                attach_to=ego if name == 'driver_reference' else None)
            owned.append(camera)
            image_queue = queue.Queue()
            camera.listen(image_queue.put)
            queues[name] = image_queue
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', str(RATE_HZ), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        first_elapsed = None
        with FrameMap(output/'video_frames.jsonl') as frame_map, (output/'visibility-trace.jsonl').open('x') as trace:
            for index in range(FRAMES):
                ego.set_target_velocity(carla.Vector3D(x=3 if index else 0, y=0, z=0))
                native_frame = world.tick()
                state = world.get_snapshot()
                if state.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                elapsed = state.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = elapsed
                ego_at = ego.get_transform().location
                vehicle_at = target.get_transform().location
                person_at = person.get_transform().location
                mapped = {}
                for name, image_queue in queues.items():
                    image = image_queue.get(timeout=30)
                    while image.frame < native_frame:
                        image = image_queue.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera frame join failed: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, elapsed-first_elapsed,
                                 camera_native_frames=mapped)
                trace.write(json.dumps({
                    'video_frame': index, 'native_frame': native_frame,
                    'time_s': elapsed-first_elapsed,
                    'ego_id': str(ego.id), 'ego_blueprint_id': ego.type_id,
                    'target_vehicle_id': str(target.id),
                    'target_vehicle_blueprint_id': target.type_id,
                    'person_id': str(person.id), 'person_blueprint_id': person.type_id,
                    'ego_xy_m': [ego_at.x, ego_at.y],
                    'target_vehicle_xy_m': [vehicle_at.x, vehicle_at.y],
                    'person_xy_m': [person_at.x, person_at.y],
                    'vehicle_forward_distance_m': vehicle_at.x-ego_at.x,
                    'person_forward_distance_m': person_at.x-ego_at.x,
                    'ego_light_state_bits': int(ego.get_light_state()),
                    'person_clearly_discernible': None,
                    'vehicle_clearly_discernible': None,
                    'camera_native_frames': mapped})+'\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: '+name+': '+stderr.decode()[-400:])
        return {'frames': FRAMES, 'source_kind': 'native_saved_sample',
                'pixel_review_required': True, 'physical_acceptance_claimed': False}
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
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--weather', choices=('ClearNoon', 'SoftRainSunset',
                                             'HardRainNoon'), default='ClearNoon')
    args = parser.parse_args()
    if args.check:
        if args.output_dir:
            raise SystemExit('--check cannot create a Native attempt')
        print(json.dumps(check(), sort_keys=True))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required for Native execution')
        print(json.dumps(execute(args.output_dir, args.host, args.port, args.weather),
                         sort_keys=True))
