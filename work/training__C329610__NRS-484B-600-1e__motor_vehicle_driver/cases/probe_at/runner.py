"""Prospective original Native left-turn absolute-speed acquisition."""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

from speed_turn import check_config

ROAD = Path(__file__).resolve().parent / 'road.xodr'
EGO_LANE_ID = -1

FRAMES = 600
RATE_HZ = 20
TARGETS_MPH = {'probe_a': 75.0, 'probe_at': 80.0, 'probe_b': 85.0}
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def check():
    road = check_config(json.loads((Path(__file__).parent/'config.json').read_text()), ROAD.read_text())
    if len(CAMERAS) != 4 or FRAMES / RATE_HZ != 30:
        raise ValueError('Speed sweep capture geometry or cadence differs')
    if not (TARGETS_MPH['probe_a'] < 80 == TARGETS_MPH['probe_at'] < TARGETS_MPH['probe_b']):
        raise ValueError('Requested speed probes do not bracket the statutory boundary')
    return {'passed': True, 'road': road, 'frames': FRAMES,
            'cameras': [row[0] for row in CAMERAS], 'carla_imported': False,
            'physical_acceptance_claimed': False}


def _camera_pose(carla, name):
    if name == 'driver_reference':
        return carla.Transform(carla.Location(x=0.7, y=0, z=1.4), carla.Rotation(pitch=-10)), True
    positions = {'overview': (-8, -35, 45, -55),
                 'approach': (-70, -12, 10, -10),
                 'reference_corner': (20, 20, 12, -20)}
    x, y, z, pitch = positions[name]
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)), False


def requested_speed(index, mph):
    seconds = (index + 1) / RATE_HZ
    high = mph * .44704
    return high if seconds <= 4 else high + (10-high)*(seconds-4)/4 if seconds <= 8 else 10


def steering_target(mapping, wp, pose):
    if wp.road_id == 1:
        target = mapping.get_waypoint_xodr(1, -1, min(422, wp.s + 12)) if wp.s < 411 else mapping.get_waypoint_xodr(13, -1, 5)
    elif wp.road_id == 13:
        target = mapping.get_waypoint_xodr(13, -1, min(12, wp.s + 5)) if wp.s < 8 else mapping.get_waypoint_xodr(4, -1, 12)
    elif wp.road_id == 4:
        target = mapping.get_waypoint_xodr(4, -1, min(wp.s + 12, 120))
    else:
        raise RuntimeError('Subject left authored left-turn route')
    if target is None:
        raise RuntimeError('Native left-turn lookahead unavailable')
    delta = target.transform.location - pose.location
    heading = math.degrees(math.atan2(delta.y, delta.x))
    error = (heading - pose.rotation.yaw + 180) % 360 - 180
    return max(-.7, min(.7, .035 * error))


def execute(case_id, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in TARGETS_MPH or not case_id.startswith('training__C329610__NRS-484B-600-1e__motor_vehicle_driver__'):
        raise ValueError('Unknown exact speed case')
    check()
    output = Path(output_dir).resolve()
    if any((output/name).exists() for name in ('video_frames.jsonl', 'native_motion.jsonl', 'road.xodr')):
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
        world = client.generate_opendrive_world(ROAD.read_text(), carla.OpendriveGenerationParameters(
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
        spawn_s_m = json.loads((Path(__file__).parent/'config.json').read_text()).get('spawn_s_m', 5)
        if spawn_s_m not in (1, 5):
            raise ValueError('Unreviewed subject spawn location')
        ego_wp = mapping.get_waypoint_xodr(1, EGO_LANE_ID, spawn_s_m)
        turn_wp = mapping.get_waypoint_xodr(13, EGO_LANE_ID, 4)
        exit_wp = mapping.get_waypoint_xodr(4, EGO_LANE_ID, 8)
        if any(wp is None for wp in (ego_wp, turn_wp, exit_wp)):
            raise RuntimeError('Native approach, left-turn arc or exit lane unavailable')
        output.mkdir(parents=True, exist_ok=True)
        (output/'road.xodr').write_text(mapping.to_opendrive())
        (output/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'physical_acceptance_claimed': False}, indent=2)+'\n')
        library = world.get_blueprint_library()
        ego_bp = library.find('vehicle.tesla.model3')
        ego_bp.set_attribute('role_name', 'c329610_speed_subject')

        ego_pose = ego_wp.transform
        ego_pose.location.z += 1
        ego = world.try_spawn_actor(ego_bp, ego_pose)
        if ego is None:
            raise RuntimeError('Native subject vehicle did not spawn')
        owned.append(ego)
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
        target_mph = TARGETS_MPH[suffix]
        with FrameMap(output/'video_frames.jsonl') as frame_map, (output/'native_motion.jsonl').open('x') as stream, (output/'trace.jsonl').open('x') as trace:
            start = None
            for index in range(FRAMES):
                pose = ego.get_transform()
                wp = mapping.get_waypoint(pose.location, project_to_road=True, lane_type=carla.LaneType.Driving)
                if wp is None or wp.road_id not in (1, 13, 4) or wp.lane_id != EGO_LANE_ID:
                    raise RuntimeError('Native ego left surveyed left-turn lane')
                speed = ego.get_velocity().length()
                target = requested_speed(index, target_mph)
                error = target-speed
                ego.apply_control(carla.VehicleControl(throttle=min(1, max(0, .35+.14*error)),
                                                       brake=min(1, max(0, -.2*error)),
                                                       steer=steering_target(mapping, wp, pose)))
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
                measured_wp = mapping.get_waypoint(pose.location, project_to_road=True, lane_type=carla.LaneType.Driving)
                if measured_wp is None or measured_wp.road_id not in (1, 13, 4) or measured_wp.lane_id != EGO_LANE_ID:
                    raise RuntimeError('Native ego left surveyed left-turn lane after tick')
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
                                         'ego_blueprint': ego.type_id, 'driving_state': True,
                                         'position_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
                                         'road_id': measured_wp.road_id, 'lane_id': measured_wp.lane_id,
                                         'controller_request_mps': target, 'velocity_x_mps': velocity.x,
                                         'velocity_y_mps': velocity.y, 'velocity_z_mps': velocity.z})+'\n')
                trace.write(json.dumps({'frame': frame, 'time_s': elapsed,
                                        'position': {'x': pose.location.x, 'y': pose.location.y,
                                                     'z': pose.location.z},
                                        'position_m': [pose.location.x, pose.location.y, pose.location.z],
                                        'heading_deg': pose.rotation.yaw,
                                        'speed_mps': math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)})+'\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError('Native source camera encoding failed: '+name+': '+stderr.decode()[-400:])
        (output/'road_context.template.json').write_text(json.dumps({
            'assignment_id': case_id.rsplit('__', 1)[0], 'case_id': case_id,
            'review_kind': 'original_source_review', 'ego_actor_id': ego.id,
            'camera_sha256': {}, 'review_required': True,
            'route_source': 'Native OpenDRIVE road.xodr plus original lane history',
            'vehicle_identity_source': 'Native vehicle blueprint and actor identity in original motion',
            'driving_state_source': 'Original Native per-frame controlled vehicle state'}, indent=2)+'\n')
        complete = True
        return {'case_id': case_id, 'frames': FRAMES, 'left_turn_route_requested': True,
                'requested_speed_mph': TARGETS_MPH[suffix], 'physical_acceptance_claimed': False}
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
                                  'absolute_speed_review': 'pending_original_source'})


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
