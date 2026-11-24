"""Survey-gated Native roundabout exit speed capture; CPU check never imports CARLA."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess
from geometry import ARC_M, check as geometry_check, open_drive

RATE = 20
FRAMES = 600
TARGET_MPS = {'controlled_1': 29.0, 'controlled_2': 38.0, 'controlled_3': 35.7632}
CAMERAS = (
    ('roundabout_overview', 1280, 720, -30, -530, 28, -45, False),
    ('arc_entry', 1280, 720, -100, -515, 14, -25, False),
    ('exit_tangent', 1280, 720, 180, -520, 14, -25, False),
    ('subject_chase', 1280, 720, -10, 0, 6, -12, True),
)

def check():
    geometry = geometry_check()
    if FRAMES / RATE != 30 or len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('four-camera 30-second capture required')
    if not (TARGET_MPS['controlled_1'] * 2.2369362921 < 80 < TARGET_MPS['controlled_2'] * 2.2369362921):
        raise ValueError('requested speeds must bracket 80 mph')
    return {'passed': True, 'frames': FRAMES, 'rate_hz': RATE, 'cameras': [c[0] for c in CAMERAS], 'geometry': geometry, 'native_imported': False, 'physical_acceptance_claimed': False}

def survey(world, carla):
    mapping = world.get_map()
    samples = []
    for road_id, s in ((1, ARC_M - 100), (1, ARC_M - 10), (2, 20), (2, 300)):
        for lane_id in (-1, -2):
            wp = mapping.get_waypoint_xodr(road_id, lane_id, s)
            if wp is None or wp.road_id != road_id or wp.lane_id != lane_id:
                raise RuntimeError(f'Native roundabout/exit lane readback differs at road={road_id}, lane={lane_id}')
            point = wp.transform.location
            samples.append({'road_id': road_id, 'lane_id': lane_id, 's_m': s, 'native_xyz_m': [point.x, point.y, point.z]})
    if len(samples) != 8:
        raise RuntimeError('Native two-lane roundabout survey incomplete')
    return samples

def execute(case_id, output_dir, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    from measure import measure
    check()
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in TARGET_MPS:
        raise ValueError('unknown exact case')
    output = Path(output_dir).resolve()
    if output.exists():
        raise ValueError('choose a fresh original Native attempt directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('requires exclusive idle asynchronous Native world')
    owned = []
    queues = {}
    encoders = {}
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(vertex_distance=.5, max_road_length=50, wall_height=0, additional_width=0, smooth_junctions=False, enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        seen = survey(world, carla)
        output.mkdir(parents=True)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'roundabout-survey.json').write_text(json.dumps(seen, indent=2) + '\n')
        library = world.get_blueprint_library()
        bp = library.find('vehicle.tesla.model3')
        bp.set_attribute('role_name', 'c131055_roundabout_speed_subject')
        spawn_wp = world.get_map().get_waypoint_xodr(1, -2, ARC_M - 100)
        spawn = spawn_wp.transform
        spawn.location.z += 1
        vehicle = world.spawn_actor(bp, spawn)
        owned.append(vehicle)
        for name, width, height, x, y, z, pitch, attached in CAMERAS:
            sensor_bp = library.find('sensor.camera.rgb')
            sensor_bp.set_attribute('image_size_x', str(width))
            sensor_bp.set_attribute('image_size_y', str(height))
            sensor_bp.set_attribute('fov', '85')
            sensor_bp.set_attribute('sensor_tick', '.05')
            transform = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch))
            camera = world.spawn_actor(sensor_bp, transform, attach_to=vehicle) if attached else world.spawn_actor(sensor_bp, transform)
            owned.append(camera)
            image_queue = queue.Queue()
            camera.listen(image_queue.put)
            queues[name] = image_queue
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}', '-r', '20', '-i', '-', '-frames:v', '600', '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'roundabout-speed-history.jsonl').open('x') as history:
            first_elapsed = None
            for index in range(FRAMES):
                current = vehicle.get_transform()
                wp = world.get_map().get_waypoint(current.location, project_to_road=True, lane_type=carla.LaneType.Driving)
                if wp is None or wp.road_id not in (1, 2) or wp.lane_id not in (-1, -2):
                    raise RuntimeError('Original subject left surveyed roundabout/exit lanes')
                ahead = wp.next(20)
                if not ahead:
                    raise RuntimeError('Native route continuation missing')
                point = ahead[0].transform.location
                desired = math.atan2(point.y - current.location.y, point.x - current.location.x)
                yaw = math.radians(current.rotation.yaw)
                error = math.atan2(math.sin(desired - yaw), math.cos(desired - yaw))
                speed = vehicle.get_velocity().length()
                target = TARGET_MPS[suffix]
                throttle = min(1.0, max(0.0, (target - speed) * .35))
                brake = min(1.0, max(0.0, (speed - target) * .3))
                steer = max(-1.0, min(1.0, error * 1.2))
                vehicle.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                absolute = snap.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = absolute
                relative = absolute - first_elapsed
                pose = vehicle.get_transform()
                velocity = vehicle.get_velocity()
                measured_wp = world.get_map().get_waypoint(pose.location, project_to_road=True, lane_type=carla.LaneType.Driving)
                if measured_wp is None or measured_wp.road_id not in (1, 2) or measured_wp.lane_id not in (-1, -2):
                    raise RuntimeError('Original post-tick lane readback missing')
                mapped = {}
                for name in queues:
                    image = queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera frame join failed: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(frame, relative, camera_native_frames=mapped)
                history.write(json.dumps({'video_frame': index, 'native_frame': frame, 'time_s': relative, 'native_elapsed_seconds': absolute, 'subject_id': vehicle.id, 'blueprint_id': vehicle.type_id, 'position_xyz_m': [pose.location.x, pose.location.y, pose.location.z], 'velocity_xyz_mps': [velocity.x, velocity.y, velocity.z], 'road_id': measured_wp.road_id, 'lane_id': measured_wp.lane_id, 'road_s_m': measured_wp.s, 'controller_request_mps': target, 'control': {'throttle': throttle, 'brake': brake, 'steer': steer}}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + stderr.decode()[-400:])
        measured = measure(output / 'roundabout-speed-history.jsonl', output / 'roundabout-survey.json')
        (output / 'roundabout-speed-measurement.json').write_text(json.dumps(measured, indent=2) + '\n')
        return {'frames': FRAMES, 'camera_names': list(queues), 'measurement': measured, 'physical_acceptance_claimed': False}
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
    p.add_argument('--case-id')
    p.add_argument('--output-dir')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=2000)
    a = p.parse_args()
    if a.check == a.execute:
        raise SystemExit('choose --check or --execute')
    if a.execute and (not a.case_id or not a.output_dir):
        raise SystemExit('--case-id and --output-dir required')
    print(json.dumps(check() if a.check else execute(a.case_id, a.output_dir, a.host, a.port)))
