"""Native roadside signal approach and source-recorded voluntary stop."""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

from road import EGO_LANE_ID, SIGNAL_STATION_M, SIGNAL_ID, check as road_check, open_drive
from case_specs import CASES
from context import spawn_context

FRAMES = 600
RATE_HZ = 20
TARGETS_FT = {name: spec['gap_ft'] for name, spec in CASES.items()}
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def check():
    road = road_check()
    if len(CAMERAS) != 4 or FRAMES / RATE_HZ != 30:
        raise ValueError('Signal approach camera or duration contract differs')
    if not (TARGETS_FT['25'] < TARGETS_FT['30'] < TARGETS_FT['35']):
        raise ValueError('Requested approach probes differ')
    return {'passed': True, 'road': road, 'frames': FRAMES,
            'cameras': [row[0] for row in CAMERAS], 'carla_imported': False,
            'physical_acceptance_claimed': False}


def _camera_pose(carla, name):
    if name == 'driver_reference':
        return carla.Transform(carla.Location(x=0.7, y=0, z=1.4), carla.Rotation(pitch=-10)), True
    positions = {'overview': (95, -18, 40, -65),
                 'approach': (82, -12, 10, -12),
                 'reference_corner': (100, -10, 12, -20)}
    x, y, z, pitch = positions[name]
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)), False


def execute(case_id, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in CASES or not case_id.startswith('training__C229987__NRS-484B-450-1g__motor_vehicle_driver__'):
        raise ValueError('Unknown exact signal approach case')
    case_config = json.loads((Path(__file__).parent/'config.json').read_text())
    if case_config.get('selected_case_id') != case_id:
        raise ValueError('Selected signal approach case differs')
    spec = CASES[suffix]
    if (case_config.get('activity_mode') != spec['activity'] or
            case_config.get('exception_request') != spec['exception'] or
            case_config.get('requested_front_gap_ft') != spec['gap_ft']):
        raise ValueError('Signal activity or exception construction differs')
    brake_lead_seconds = float(case_config.get('brake_lead_seconds', 1.2))
    if not 1.0 <= brake_lead_seconds <= 2.0:
        raise ValueError('Signal approach brake lead outside tested engineering range')
    check()
    output = Path(output_dir).resolve()
    if any((output/name).exists() for name in ('video_frames.jsonl', 'signal_raw.json', 'road.xodr')):
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
        ego_wp = mapping.get_waypoint_xodr(1, EGO_LANE_ID, 65)
        if ego_wp is None:
            raise RuntimeError('Native signal approach lane unavailable')
        heads = [actor for actor in world.get_actors().filter('traffic.traffic_light*')
                 if str(actor.get_opendrive_id()) == SIGNAL_ID]
        if len(heads) != 1:
            raise RuntimeError('Exactly one specified roadside signal actor required')
        head = heads[0]
        governed = any(w.road_id == 1 and w.lane_id == EGO_LANE_ID
                       for w in head.get_affected_lane_waypoints())
        if not governed:
            raise RuntimeError('Signal does not govern the selected approach lane')
        signal_pose = head.get_transform()
        if abs(signal_pose.location.x-SIGNAL_STATION_M) > 6:
            raise RuntimeError('Native signal roadside location differs from specification')
        head.set_state(carla.TrafficLightState.Red if spec['exception'] in
                       ('other_law','device_direction') else carla.TrafficLightState.Green)
        head.freeze(True)
        output.mkdir(parents=True, exist_ok=True)
        (output/'road.xodr').write_text(mapping.to_opendrive())
        (output/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'physical_acceptance_claimed': False}, indent=2)+'\n')
        library = world.get_blueprint_library()
        ego_bp = library.find('vehicle.tesla.model3')
        ego_bp.set_attribute('role_name', 'c229987_signal_approach_subject')
        ego_pose = ego_wp.transform
        ego_pose.location.z += 1
        ego = world.try_spawn_actor(ego_bp, ego_pose)
        if ego is None:
            raise RuntimeError('Native subject did not spawn')
        owned.append(ego)
        requested_front_gap_m = TARGETS_FT[suffix]*.3048
        target_center_x = SIGNAL_STATION_M-requested_front_gap_m-2.25
        context_actors, context_requests = spawn_context(
            world, carla, library, spec['activity'], spec['exception'], target_center_x)
        owned.extend(context_actors)
        capture = PipelineCapture(client, ego, output, case_id,
                                  visibility=False,
                                  required_observations=case_config.get('required_atoms', []))
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
        signal_frames = []
        with FrameMap(output/'video_frames.jsonl') as frame_map, (output/'trace.jsonl').open('x') as trace:
            start = None
            for index in range(FRAMES):
                pose = ego.get_transform()
                remaining = target_center_x-pose.location.x
                velocity_before = ego.get_velocity().length()
                # This is a motion attempt. Original footprint and halt reason are reviewed later.
                ego.apply_control(carla.VehicleControl(
                    throttle=.25 if remaining > max(2, velocity_before*brake_lead_seconds) else 0,
                    brake=1.0 if remaining <= max(2, velocity_before*brake_lead_seconds) else 0,
                    hand_brake=spec['activity'] in ('stand','park') and
                               remaining <= .7 and velocity_before < .4, steer=0))
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
                measured_wp = mapping.get_waypoint(pose.location, project_to_road=True,
                                                   lane_type=carla.LaneType.Driving)
                if measured_wp is None or measured_wp.road_id != 1 or measured_wp.lane_id != EGO_LANE_ID:
                    raise RuntimeError('Native ego left signal approach lane')
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
                extent = ego.bounding_box.extent
                corners = []
                for dx in (-extent.x, extent.x):
                    for dy in (-extent.y, extent.y):
                        local = carla.Location(x=dx, y=dy, z=0)
                        world_point = pose.transform(local)
                        corners.append({'x_m': world_point.x, 'y_m': world_point.y})
                speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                signal_frames.append({'time_s': elapsed, 'speed_mps': speed,
                                      'vehicle_footprint_xy_m': corners,
                                      'native_frame': frame,
                                      'signal_state': str(head.get_state()),
                                      'signal_actor_id': head.id,
                                      'ego_actor_id': ego.id,
                                      'road_id': measured_wp.road_id,
                                      'lane_id': measured_wp.lane_id,
                                      'requested_front_gap_m': requested_front_gap_m})
                trace.write(json.dumps({'frame': frame, 'time_s': elapsed,
                                        'position': {'x': pose.location.x, 'y': pose.location.y,
                                                     'z': pose.location.z},
                                        'position_m': [pose.location.x, pose.location.y, pose.location.z],
                                        'heading_deg': pose.rotation.yaw,
                                        'speed_mps': speed})+'\n')
        (output/'signal_raw.json').write_text(json.dumps({
            'assignment_id': case_id.rsplit('__', 1)[0],
            'source_kind': 'native_raw_capture',
            'road_geometry': {'approach_origin': {'x_m': 0, 'y_m': 0},
                              'approach_tangent': {'x_m': 1, 'y_m': 0}},
            'signal': {'roadside_position': {'x_m': signal_pose.location.x,
                                             'y_m': signal_pose.location.y},
                       'actor_id': head.id, 'opendrive_id': SIGNAL_ID,
                       'governs_lane': governed},
            'geometry_uncertainty_m': .05,
            'constructed_context': {'activity_request': spec['activity'],
                                    'exception_request': spec['exception'],
                                    'actor_ids': [actor.id for actor in context_actors],
                                    'actor_requests': context_requests},
            'context_sources': {key: 'context-survey.json' for key in (
                'highway_status_source', 'official_signal_status_source',
                'roadside_placement_source', 'governed_movement_source',
                'signal_indication_source', 'halt_purpose_source',
                'other_traffic_source', 'applicable_law_source',
                'officer_direction_source', 'device_direction_source')},
            'frames': signal_frames}, separators=(',', ':'))+'\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError('Native source camera encoding failed: '+name+': '+stderr.decode()[-400:])
        (output/'context-survey.template.json').write_text(json.dumps({
            'case_id': case_id, 'review_kind': 'original_source_review',
            'activity_request': spec['activity'],
            'exception_request': spec['exception'],
            'constructed_context_actor_ids': [actor.id for actor in context_actors],
            'highway_status': None, 'official_signal_status': None,
            'signal_governs_selected_lane_native': governed,
            'signal_actor_id': head.id, 'signal_opendrive_id': SIGNAL_ID,
            'halt_purpose': None, 'other_traffic_conflict': None,
            'applicable_law_direction': None, 'officer_direction': None,
            'device_direction': None, 'independent_reviewer': None,
            'actual_pixels_reviewed': None, 'approach_geometry_reviewed': None,
            'signal_raw_sha256': None, 'road_sha256': None}, indent=2)+'\n')
        complete = True
        return {'case_id': case_id, 'frames': FRAMES, 'signal_actor_id': head.id,
                'requested_front_gap_ft': TARGETS_FT[suffix], 'physical_acceptance_claimed': False}
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
                                  'roadside_signal_review': 'pending_original_source'})


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
