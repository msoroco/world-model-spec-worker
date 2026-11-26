"""Native basic-speed sweep with frame-joined traffic and conditions."""
import argparse
import json
import math
import hashlib
import queue
import subprocess
from pathlib import Path

from road import EGO_LANE_ID, OTHER_LANE_ID, LENGTH_M, check as road_check, open_drive

FRAMES = 600
RATE_HZ = 20
TARGETS_MPS = {'8': 8.0, '12': 12.0, '16': 16.0, '20': 20.0}
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def check():
    road = road_check()
    if len(CAMERAS) != 4 or FRAMES / RATE_HZ != 30 or LENGTH_M < 1500:
        raise ValueError('Speed sweep capture geometry or cadence differs')
    if sorted(TARGETS_MPS.values()) != [8.0, 12.0, 16.0, 20.0]:
        raise ValueError('Requested engineering speed sweep changed')
    return {'passed': True, 'road': road, 'frames': FRAMES,
            'cameras': [row[0] for row in CAMERAS], 'carla_imported': False,
            'physical_acceptance_claimed': False}


def _camera_pose(carla, name):
    if name == 'driver_reference':
        return carla.Transform(carla.Location(x=0.7, y=0, z=1.4), carla.Rotation(pitch=-10)), True
    positions = {'overview': (600, -35, 65, -60),
                 'approach': (100, -20, 15, -20),
                 'reference_corner': (1000, -20, 15, -20)}
    x, y, z, pitch = positions[name]
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)), False


def execute(case_id, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in TARGETS_MPS or not case_id.startswith('training__C230259__NRS-484B-600-1a__motor_vehicle_driver__'):
        raise ValueError('Unknown exact speed case')
    check()
    output = Path(output_dir).resolve()
    if any((output/name).exists() for name in ('video_frames.jsonl', 'native_motion.jsonl', 'conditions.jsonl', 'road.xodr')):
        raise ValueError('Retain prior Native source; use a fresh attempt')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = snapshot(client)
    old_world = client.get_world()
    if prior['settings'].synchronous_mode or any(actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.')) for actor in old_world.get_actors()):
        raise RuntimeError('Requires an exclusive idle asynchronous Native world')
    owned, encoders, queues = [], {}, {}
    capture = None
    complete = False
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=1, max_road_length=50, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        mapping = world.get_map()
        ego_wp = mapping.get_waypoint_xodr(1, EGO_LANE_ID, 5)
        other_wp = mapping.get_waypoint_xodr(1, OTHER_LANE_ID, 100)
        far_wp = mapping.get_waypoint_xodr(1, EGO_LANE_ID, 1500)
        if any(wp is None for wp in (ego_wp, other_wp, far_wp)):
            raise RuntimeError('Native clear corridor or separate other-vehicle lane unavailable')
        output.mkdir(parents=True, exist_ok=True)
        (output/'road.xodr').write_text(mapping.to_opendrive())
        map_sha256 = hashlib.sha256((output/'road.xodr').read_bytes()).hexdigest()
        (output/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'physical_acceptance_claimed': False}, indent=2)+'\n')
        library = world.get_blueprint_library()
        ego_bp = library.find('vehicle.tesla.model3')
        ego_bp.set_attribute('role_name', 'c230259_speed_subject')
        other_bp = library.find('vehicle.tesla.model3')
        other_bp.set_attribute('role_name', 'c230259_other_vehicle')
        ego_pose = ego_wp.transform
        ego_pose.location.z += 1
        other_pose = other_wp.transform
        other_pose.location.z += 1
        ego = world.try_spawn_actor(ego_bp, ego_pose)
        other = world.try_spawn_actor(other_bp, other_pose)
        if ego is None or other is None or ego.id == other.id:
            raise RuntimeError('Separate Native vehicles did not spawn')
        owned.extend((ego, other))
        other.set_simulate_physics(False)
        capture = PipelineCapture(client, ego, output, case_id,
                                  visibility=False,
                                  required_observations=json.loads((Path(__file__).parent/'config.json').read_text()).get('required_atoms', []))
        for name, width, height in CAMERAS:
            camera_bp = library.find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', str(width))
            camera_bp.set_attribute('image_size_y', str(height))
            camera_bp.set_attribute('sensor_tick', '.05')
            camera_bp.set_attribute('fov', '85')
            pose, attached = _camera_pose(carla, name)
            camera = world.spawn_actor(camera_bp, pose, attach_to=ego if attached else None)
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                                               '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                                               '-r', str(RATE_HZ), '-i', '-', '-frames:v', str(FRAMES),
                                               '-c:v', 'ffv1', '-level', '1', str(output/(name+'.mkv'))],
                                              stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        target = TARGETS_MPS[suffix]
        with FrameMap(output/'video_frames.jsonl') as frame_map, (output/'native_motion.jsonl').open('x') as stream, (output/'conditions.jsonl').open('x') as conditions, (output/'trace.jsonl').open('x') as trace:
            start = None
            for index in range(FRAMES):
                pose = ego.get_transform()
                wp = mapping.get_waypoint(pose.location, project_to_road=True, lane_type=carla.LaneType.Driving)
                if wp is None or wp.road_id != 1 or wp.lane_id != EGO_LANE_ID:
                    raise RuntimeError('Native ego left surveyed speed lane')
                speed = ego.get_velocity().length()
                error = target-speed
                ego.apply_control(carla.VehicleControl(throttle=min(1, max(0, .35+.14*error)),
                                                       brake=min(1, max(0, -.2*error)), steer=0))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('Native snapshot frame mismatch')
                if start is None:
                    start = snap.timestamp.elapsed_seconds
                elapsed = snap.timestamp.elapsed_seconds-start
                capture.capture(frame, elapsed)
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                other_pose = other.get_transform()
                measured_wp = mapping.get_waypoint(pose.location, project_to_road=True, lane_type=carla.LaneType.Driving)
                if measured_wp is None or measured_wp.road_id != 1 or measured_wp.lane_id != EGO_LANE_ID:
                    raise RuntimeError('Native ego left surveyed speed lane after tick')
                joined = {}
                for name, q in queues.items():
                    image = q.get(timeout=30)
                    while image.frame < frame:
                        image = q.get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Native camera source frame mismatch: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    joined[name] = frame
                frame_map.append(frame, elapsed, camera_native_frames=joined)
                stream.write(json.dumps({'video_frame': index, 'native_frame': frame, 'time_s': elapsed,
                                         'source_kind': 'original_native_velocity', 'ego_actor_id': ego.id,
                                         'other_actor_id': other.id, 'ego_blueprint': ego.type_id,
                                         'other_blueprint': other.type_id, 'driving_state': True,
                                         'position_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
                                         'other_position_xyz_m': [other_pose.location.x, other_pose.location.y, other_pose.location.z],
                                         'road_id': measured_wp.road_id, 'lane_id': measured_wp.lane_id,
                                         'controller_request_mps': target, 'velocity_x_mps': velocity.x,
                                         'velocity_y_mps': velocity.y, 'velocity_z_mps': velocity.z})+'\n')
                other_velocity = other.get_velocity()
                native_weather = world.get_weather()
                conditions.write(json.dumps({
                    'video_frame': index, 'native_frame': frame, 'time_s': elapsed,
                    'camera_frames': joined,
                    'ego_velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
                    'traffic': [{'native_actor_id': other.id,
                                 'velocity_xyz_mps': [other_velocity.x, other_velocity.y, other_velocity.z],
                                 'class_source': 'Native blueprint '+other.type_id}],
                    'road': {'native_map_sha256': map_sha256,
                             'surface_source': 'Native weather wetness and map geometry; pavement material unresolved',
                             'surface_wetness': native_weather.wetness,
                             'lane_width_m': measured_wp.lane_width,
                             'curvature_inv_m': 0.0},
                    'weather': {'precipitation': native_weather.precipitation,
                                'fog_density': native_weather.fog_density,
                                'sun_altitude_angle': native_weather.sun_altitude_angle},
                    'visibility_source': 'Native fog-density readback and original source cameras'
                })+'\n')
                trace.write(json.dumps({'frame': frame, 'time_s': elapsed,
                                        'position': {'x': pose.location.x, 'y': pose.location.y,
                                                     'z': pose.location.z},
                                        'position_m': [pose.location.x, pose.location.y, pose.location.z],
                                        'heading_deg': pose.rotation.yaw,
                                        'speed_mps': math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
                                        'speed_mph': math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)/0.44704})+'\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError('Native source camera encoding failed: '+name+': '+stderr.decode()[-400:])
        (output/'road_context.template.json').write_text(json.dumps({
            'assignment_id': case_id.rsplit('__', 1)[0], 'case_id': case_id,
            'review_kind': 'original_source_review', 'ego_actor_id': ego.id,
            'other_actor_id': other.id, 'camera_sha256': {}, 'review_required': True,
            'route_source': 'Native OpenDRIVE road.xodr plus original lane history',
            'vehicle_identity_source': 'Native vehicle blueprint and actor identity in original motion',
            'other_vehicle_source': 'Separate Native other vehicle actor and original relative pose',
            'driving_state_source': 'Original Native per-frame controlled vehicle state'}, indent=2)+'\n')
        complete = True
        return {'case_id': case_id, 'frames': FRAMES, 'separate_other_vehicle': True,
                'requested_speed_mps': TARGETS_MPS[suffix], 'physical_acceptance_claimed': False}
    except BaseException as error:
        (output/'native-run-status.json').write_text(json.dumps({
            'errors': [str(error)], 'frames_complete': complete,
            'physical_acceptance_claimed': False}, indent=2)+'\n')
        raise
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
        restoration = restore(client, prior) if changed else {'restored': True, 'world_unchanged': True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                         encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                         context={'case_id': case_id, 'candidate_id': 'primary',
                                  'basic_speed_review': 'pending_original_source'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case-id')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    elif args.output_dir:
        config = json.loads((Path(__file__).parent/'config.json').read_text())
        case_id = args.case_id or config.get('selected_case_id')
        if case_id != config.get('selected_case_id'):
            raise ValueError('Native case differs from exact materialized bundle')
        print(json.dumps(execute(case_id, args.output_dir, args.host, args.port)))
    else:
        parser.error('Supply --output-dir for Native capture')
