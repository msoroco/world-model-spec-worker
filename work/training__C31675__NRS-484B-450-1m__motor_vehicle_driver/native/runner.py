"""Original four-camera bridge-halt capture; CARLA is imported only on execution."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from controller import START_X_M, TARGET_X_M, check as controller_check, command
from geometry import (DECK_POLYGON_XY_M, LANE_CENTER_Y_M, check as geometry_check,
                      elevation, open_drive)

FRAMES = 600
RATE = 20
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
MOUNTS = {'overview': (25, -24, 25, -35), 'approach': (-25, -12, 9, -16),
          'reference_corner': (80, 10, 12, -24), 'driver_reference': (5, 8, 7, -18)}


def check(config):
    geometry_check()
    controller_check()
    if (config['law_id'], config['cell_id'], config['actor']) != (
            'NRS-484B-450-1m', 'C31675', 'motor_vehicle_driver'):
        raise ValueError('exact bridge assignment identity changed')
    if config['case_id'].rsplit('__', 1)[-1] not in TARGET_X_M:
        raise ValueError('unknown exact bridge comparison case')
    if config['rate_hz'] != RATE or config['duration_s'] != 30:
        raise ValueError('600-frame 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four original bridge cameras required')
    return {'frames': FRAMES, 'rate_hz': RATE, 'cameras': CAMERAS,
            'original_native_executed': False, 'physical_bridge_verified': False,
            'exception_or_legal_result': None}


def survey(carla, mapping):
    rows = []
    for x in (-75.0, -25.0, 0.0, 50.0, 100.0, 175.0):
        wp = mapping.get_waypoint(carla.Location(x=x, y=LANE_CENTER_Y_M,
                                                   z=elevation(x) + 1.4),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1:
            raise RuntimeError('Native bridge lane readback differs')
        p = wp.transform.location
        if abs(p.x - x) > 1.0 or abs(p.y - LANE_CENTER_Y_M) > .8 or abs(p.z - elevation(x)) > 1.0:
            raise RuntimeError('Native bridge elevation readback differs')
        rows.append({'requested_x_m': x, 'native_xyz_m': [p.x, p.y, p.z],
                     'road_id': wp.road_id, 'lane_id': wp.lane_id})
    return rows


def footprint(actor):
    pose, extent = actor.get_transform(), actor.bounding_box.extent
    angle = math.radians(pose.rotation.yaw)
    c, s = math.cos(angle), math.sin(angle)
    return [[pose.location.x + c * dx - s * dy,
             pose.location.y + s * dx + c * dy]
            for dx, dy in ((-extent.x, -extent.y), (extent.x, -extent.y),
                           (extent.x, extent.y), (-extent.x, extent.y))]


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or any((output / name).exists() for name in
                                  ('video_frames.jsonl', 'bridge-trace.jsonl', 'bridge-map.json')):
        raise ValueError('fresh materialized attempt directory required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    previous = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in previous.get_actors()):
        raise RuntimeError('exclusive idle Native world required')
    owned, encoders, queues = [], {}, {}
    changed = complete = False
    capture = None
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
        rows = survey(carla, world.get_map())
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'bridge-map.json').write_text(json.dumps({
            'source_kind': 'native_bridge_lane_survey', 'structure_type': 'bridge',
            'deck_polygon_xy_m': DECK_POLYGON_XY_M, 'native_lane_survey': rows,
            'physical_support_verified': False, 'original_pixels_verified': False}) + '\n')
        library = world.get_blueprint_library()
        bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        bp.set_attribute('role_name', 'c31675_bridge_subject')
        ego = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=config.get('initial_spawn_x_m', START_X_M),
                           y=LANE_CENTER_Y_M, z=2.0),
            carla.Rotation(yaw=0)))
        owned.append(ego)
        other_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        other_bp.set_attribute('role_name', 'c31675_other_vehicle')
        other = world.spawn_actor(other_bp, carla.Transform(
            carla.Location(x=120, y=1.75, z=7.0), carla.Rotation(yaw=180)))
        owned.append(other)
        other.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False,
                                  required_observations=config.get('required_atoms', []))
        for name in CAMERAS:
            spec = next(v for v in config['cameras'] if v['name'] == name)
            sensor = library.find('sensor.camera.rgb')
            sensor.set_attribute('image_size_x', str(spec['width']))
            sensor.set_attribute('image_size_y', str(spec['height']))
            sensor.set_attribute('sensor_tick', str(1 / RATE))
            sensor.set_attribute('fov', str(spec['fov_deg']))
            x, y, z, pitch = MOUNTS[name]
            camera = world.spawn_actor(sensor, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        suffix = config['case_id'].rsplit('__', 1)[-1]
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'bridge-trace.jsonl').open('x') as bridge_trace, \
                (output / 'trace.jsonl').open('x') as trace:
            initial_time = None
            for index in range(FRAMES):
                pose, vel = ego.get_transform(), ego.get_velocity()
                speed = math.sqrt(vel.x * vel.x + vel.y * vel.y + vel.z * vel.z)
                request = command(suffix, index, pose.location.x, speed)
                ego.apply_control(carla.VehicleControl(throttle=request['throttle'],
                    brake=request['brake'], steer=request['steer']))
                other.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                capture.capture(native_frame, time_s)
                camera_frames = {}
                for name, q in queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                pose, vel = ego.get_transform(), ego.get_velocity()
                speed = math.sqrt(vel.x * vel.x + vel.y * vel.y + vel.z * vel.z)
                bridge_trace.write(json.dumps({'frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'speed_mps': speed,
                    'body_footprint_xy_m': footprint(ego),
                    'requested_halt_cause': 'voluntary_destination',
                    'requested_control': request, 'other_actor_id': other.id,
                    'other_position_xyz_m': [other.get_transform().location.x,
                                             other.get_transform().location.y,
                                             other.get_transform().location.z],
                    'exception_verified': False}) + '\n')
                trace.write(json.dumps({'frame': native_frame, 'time_s': time_s,
                    'position': {'x': pose.location.x, 'y': pose.location.y,
                                 'z': pose.location.z},
                    'position_m': [pose.location.x, pose.location.y, pose.location.z],
                    'heading_deg': pose.rotation.yaw, 'speed_mps': speed,
                    'speed_mph': speed * 2.2369362921,
                    'velocity_mps': [vel.x, vel.y, vel.z], 'control': request}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        complete = True
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'ego_actor_id': ego.id, 'other_actor_id': other.id,
                'physical_bridge_and_exception_review_required': True}
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
        restored = restore(client, saved) if changed else {'restored': True,
                                                              'world_unchanged': True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                encoder_exit_codes={name: p.returncode for name, p in encoders.items()},
                context={'case_id': config['case_id'],
                         'candidate_id': config.get('candidate_id', 'primary'),
                         'bridge_and_exception_review': 'pending'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required')
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
