"""Survey-gated 30-second Native bus terminus capture. CPU check avoids CARLA import."""
import argparse
import json
import queue
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from geometry import check as geometry_check, open_drive

RATE = 20
FRAMES = 600
CAMERAS = (
    ('terminus_overview', 1280, 720, 10, -22, 18, -42, False),
    ('terminus_marker', 1280, 720, -8, -13, 6, -18, False),
    ('parking_zone', 1280, 720, 12, -15, 8, -35, False),
    ('bus_chase', 1280, 720, -8, 0, 5, -10, True),
)
DWELL_TARGET_S = {'probe_01': 8.0, 'probe_02': 18.0}

def check():
    geo = geometry_check()
    if FRAMES / RATE != 30 or len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('four-camera 30-second capture required')
    if not (0 < DWELL_TARGET_S['probe_01'] < DWELL_TARGET_S['probe_02'] < 25):
        raise ValueError('dwell comparison changed')
    return {'passed': True, 'frames': FRAMES, 'rate_hz': RATE, 'cameras': [c[0] for c in CAMERAS], 'geometry': geo, 'native_imported': False, 'physical_acceptance_claimed': False}

def survey(world, carla):
    mapping = world.get_map()
    root = ET.fromstring(mapping.to_opendrive())
    signs = root.findall('.//signal')
    if len(signs) != 1 or signs[0].attrib.get('name') != 'BUS ROUTE TERMINUS':
        raise RuntimeError('Native route terminus marker readback differs')
    if signs[0].attrib.get('unit') != 'none':
        raise RuntimeError('Native marker unexpectedly declares a duration')
    samples = []
    for x in (-12, 0, 10, 20):
        loc = carla.Location(x=x, y=-5.25, z=1)
        wp = mapping.get_waypoint(loc, project_to_road=True, lane_type=carla.LaneType.Parking)
        if wp is None or wp.road_id != 1 or wp.lane_id != -2:
            raise RuntimeError(f'Native parking-zone lane readback differs at x={x}')
        p = wp.transform.location
        if abs(p.x - x) > 1 or abs(p.y + 5.25) > 1:
            raise RuntimeError(f'Native parking-zone geometry differs at x={x}')
        samples.append({'requested_x_m': x, 'native_xyz_m': [p.x, p.y, p.z], 'road_id': wp.road_id, 'lane_id': wp.lane_id})
    return {'terminus_signal': signs[0].attrib, 'parking_lane_samples': samples, 'sign_pixels_verified': False, 'official_designation_verified': False}

def execute(case_id, output_dir, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    from measure import measure
    check()
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in DWELL_TARGET_S:
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
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0, smooth_junctions=False, enable_mesh_visibility=True, enable_pedestrian_navigation=False))
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
        context = {'zone_x_m': [-2.0, 20.0], 'parking_lane_id': -2, 'native_survey': seen, 'covered_non_tour_bus_claim': 'vehicle.mitsubishi.fusorosa', 'operator_id': 'authored-bus-controller', 'designation_authority_source': None, 'designated_period_s': None, 'designation_verified': False, 'actual_loading_activity_verified': False, 'physical_sign_pixels_verified': False}
        (output / 'terminus-context.json').write_text(json.dumps(context, indent=2) + '\n')
        library = world.get_blueprint_library()
        bp = library.find('vehicle.mitsubishi.fusorosa')
        bp.set_attribute('role_name', 'c393261_route_bus')
        bus = world.spawn_actor(bp, carla.Transform(carla.Location(x=-12, y=-5.25, z=1), carla.Rotation(yaw=0)))
        owned.append(bus)
        for name, width, height, x, y, z, pitch, attached in CAMERAS:
            sensor_bp = library.find('sensor.camera.rgb')
            sensor_bp.set_attribute('image_size_x', str(width))
            sensor_bp.set_attribute('image_size_y', str(height))
            sensor_bp.set_attribute('fov', '85')
            sensor_bp.set_attribute('sensor_tick', '.05')
            transform = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch))
            camera = world.spawn_actor(sensor_bp, transform, attach_to=bus) if attached else world.spawn_actor(sensor_bp, transform)
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}', '-r', '20', '-i', '-', '-frames:v', '600', '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        state = 'approach'
        parked_since = None
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'terminus-history.jsonl').open('x') as history:
            first_time = None
            for index in range(FRAMES):
                pose_before = bus.get_transform()
                speed_before = bus.get_velocity().length()
                if state == 'approach':
                    if pose_before.location.x >= 0 and speed_before < .25:
                        state = 'parked'
                    control = carla.VehicleControl(throttle=.23 if pose_before.location.x < -1 else 0, brake=1 if pose_before.location.x >= -1 else 0, hand_brake=False)
                elif state == 'parked':
                    control = carla.VehicleControl(throttle=0, brake=1, hand_brake=True)
                else:
                    control = carla.VehicleControl(throttle=.35, brake=0, hand_brake=False)
                bus.apply_control(control)
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                absolute = snap.timestamp.elapsed_seconds
                if first_time is None:
                    first_time = absolute
                relative = absolute - first_time
                pose = bus.get_transform()
                velocity = bus.get_velocity()
                speed = velocity.length()
                if state == 'approach' and pose.location.x >= -1 and speed < .25:
                    state = 'parked'
                    parked_since = relative
                if state == 'parked' and parked_since is not None and relative - parked_since >= DWELL_TARGET_S[suffix]:
                    state = 'depart'
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
                history.write(json.dumps({'video_frame': index, 'native_frame': frame, 'time_s': relative, 'native_elapsed_seconds': absolute, 'subject_id': bus.id, 'blueprint_id': bus.type_id, 'position_xyz_m': [pose.location.x, pose.location.y, pose.location.z], 'velocity_xyz_mps': [velocity.x, velocity.y, velocity.z], 'controller_state': state, 'control': {'throttle': control.throttle, 'brake': control.brake, 'hand_brake': control.hand_brake}}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + stderr.decode()[-400:])
        measured = measure(output / 'terminus-history.jsonl', output / 'terminus-context.json')
        (output / 'terminus-measurement.json').write_text(json.dumps(measured, indent=2) + '\n')
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
