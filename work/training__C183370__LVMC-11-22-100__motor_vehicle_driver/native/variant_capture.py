"""Source-only CARLA acquisition for C183370 statutory control variants.

The pre-existing control actor and route are verified before ego spawn. Camera
pixels and original actor motion are retained; no warning, repair or legal
finding is inferred from an authored survey.
"""
import copy
import json
import queue
import sys
from math import atan2, degrees, hypot
from pathlib import Path

from capture import CAMERAS, FFV1Sink, install_cameras
from route_control import RouteControl
from statutory_variants import bind


def sample(world, carla, ego, control, command):
    if control is None:
        raise ValueError('Original control actor disappeared')
    pose = ego.get_transform()
    location = pose.location
    velocity = ego.get_velocity()
    vertices = ego.bounding_box.get_world_vertices(pose)
    if len(vertices) != 8:
        raise ValueError('Original vehicle body needs eight vertices')
    waypoint = world.get_map().get_waypoint(
        location, project_to_road=False, lane_type=carla.LaneType.Any)
    if waypoint is None or waypoint.lane_type not in (
            carla.LaneType.Driving, carla.LaneType.Shoulder):
        raise ValueError('Original vehicle left drivable pavement')
    actor_location = control.get_transform().location
    speed = hypot(hypot(velocity.x, velocity.y), velocity.z)
    return {'source_kind': 'original_carla_actor_and_map_readback',
            'ego_actor_id': ego.id, 'ego_type_id': ego.type_id,
            'ego_position_xyz_m': [location.x, location.y, location.z],
            'ego_yaw_deg': pose.rotation.yaw,
            'ego_velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'ego_speed_mps': speed,
            'ego_body_vertices_xyz_m': [[v.x, v.y, v.z] for v in vertices],
            'ego_road_id': waypoint.road_id, 'ego_lane_id': waypoint.lane_id,
            'ego_lane_type': str(waypoint.lane_type),
            'control_actor_id': control.id, 'control_type_id': control.type_id,
            'control_xyz_m': [actor_location.x, actor_location.y, actor_location.z],
            'requested_control': command, 'control_content_verified': False,
            'employee_exception_verified': False,
            'physical_completion_claimed': False}


def acquire(survey, case, attempt, client, carla, *, sink_factory=FFV1Sink):
    """Capture an exact variant case into a fresh ignored runtime attempt."""
    attempt = Path(attempt).resolve()
    from pathing import repository_root
    repo = repository_root(__file__)
    if not attempt.is_relative_to((repo / '.runtime-work').resolve()):
        raise ValueError('Variant attempt must stay under .runtime-work')
    if not attempt.is_dir():
        raise ValueError('Exact variant bundle must be materialized first')
    config_path = attempt / 'config.json'
    selected = attempt / 'candidate-selection.json'
    construction = attempt / 'construction.json'
    if not all(path.is_file() for path in (config_path, selected, construction)):
        raise ValueError('Exact variant selection/config/construction missing')
    config = json.loads(config_path.read_text())
    selection = json.loads(selected.read_text())
    import hashlib
    if (config.get('case_suffix') != case or
            config.get('selected_case_id') != selection.get('case_id') or
            config.get('case_id') != selection.get('case_id') or
            selection.get('construction_sha256') != hashlib.sha256(construction.read_bytes()).hexdigest() or
            config.get('frames') != survey.get('frames')):
        raise ValueError('Exact variant selection/config differs')
    if any((attempt / name).exists() for name in
           ('capture-receipt.json', 'native-actors.jsonl', 'video_frames.jsonl', 'trace.jsonl')):
        raise ValueError('Preserve prior variant capture; use a fresh attempt')
    world = client.get_world()
    readback = bind(survey, world, carla)
    if case not in readback['plan']['cases']:
        raise ValueError('Case is not in surveyed statutory variant')
    route = readback['plan']['cases'][case]['route_xy_m']
    first, second = route[:2]
    yaw = degrees(atan2(second[1] - first[1], second[0] - first[0]))
    transform = carla.Transform(
        carla.Location(x=first[0], y=first[1], z=survey['anchor_z_m'] + .25),
        carla.Rotation(yaw=yaw))
    original_settings = world.get_settings()
    settings = copy.copy(original_settings)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = .05
    ego = None
    sensors = []
    sinks = {}
    (attempt / 'live-readback.json').write_text(json.dumps(readback, indent=2) + '\n')
    (attempt / 'road.xodr').write_text(world.get_map().to_opendrive())
    callbacks = {name: queue.Queue() for name, *_ in CAMERAS}
    controller = RouteControl(route, **config['controller_knobs'])
    prior_frame = -1
    prior_time = -1.0
    try:
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        ego = world.try_spawn_actor(library.find(survey['ego_blueprint']), transform)
        if ego is None:
            raise ValueError('Variant ego spawn is occupied')
        control = world.get_actors().find(survey['control_actor_id'])
        sensors = install_cameras(world, library, carla, ego, callbacks,
                                  config.get('camera_overrides'))
        for name, width, height, *_ in CAMERAS:
            sinks[name] = sink_factory(attempt / (name + '.mkv'), width, height)
        with (attempt / 'native-actors.jsonl').open('x') as actors, \
             (attempt / 'video_frames.jsonl').open('x') as frames, \
             (attempt / 'trace.jsonl').open('x') as trace:
            for index in range(survey['frames']):
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = hypot(hypot(velocity.x, velocity.y), velocity.z)
                command = controller.decide(pose.location.x, pose.location.y,
                                            pose.rotation.yaw, speed)
                ego.apply_control(carla.VehicleControl(
                    throttle=command['throttle'], brake=command['brake'],
                    steer=command['steer']))
                frame = world.tick()
                if type(frame) is not int or frame <= prior_frame:
                    raise ValueError('Original CARLA frame did not advance')
                prior_frame = frame
                for name, *_ in CAMERAS:
                    image = callbacks[name].get(timeout=10)
                    if image.frame != frame:
                        raise ValueError('Variant source camera frame mismatch: ' + name)
                    sinks[name].write(image)
                timestamp = world.get_snapshot().timestamp.elapsed_seconds
                if timestamp <= prior_time:
                    raise ValueError('Original CARLA time did not advance')
                prior_time = timestamp
                frames.write(json.dumps({'video_frame': index, 'carla_frame': frame,
                                         'native_frame': frame, 'time_s': timestamp}) + '\n')
                observed = sample(world, carla, ego, control, command)
                actors.write(json.dumps(dict(observed, frame=frame,
                                             video_frame=index, time_s=timestamp),
                                        allow_nan=False) + '\n')
                trace.write(json.dumps({
                    'frame': frame, 'time_s': timestamp,
                    'position_m': observed['ego_position_xyz_m'][:2],
                    'position': dict(zip(('x', 'y', 'z'), observed['ego_position_xyz_m'])),
                    'heading_deg': observed['ego_yaw_deg'],
                    'speed_mps': observed['ego_speed_mps'],
                    'speed_mph': observed['ego_speed_mps'] / .44704,
                    'velocity_mps': observed['ego_velocity_xyz_mps'],
                    'speed_provenance': 'original_carla_velocity',
                    'control': command}, allow_nan=False) + '\n')
    finally:
        active_error = sys.exc_info()[0] is not None
        errors = []
        if ego is not None:
            try:
                ego.apply_control(carla.VehicleControl(throttle=0, brake=1))
            except Exception as error:
                errors.append(error)
        for sensor in reversed(sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception as error:
                errors.append(error)
        for sink in sinks.values():
            try:
                sink.close()
            except Exception as error:
                errors.append(error)
        if ego is not None:
            try:
                ego.destroy()
            except Exception as error:
                errors.append(error)
        try:
            world.apply_settings(original_settings)
        except Exception as error:
            errors.append(error)
        if errors and not active_error:
            raise errors[0]
    receipt = {'source_frames': survey['frames'], 'capture_rate_hz': 20,
               'case': case, 'control_kind': survey['control_kind'],
               'four_cameras': [name + '.mkv' for name, *_ in CAMERAS],
               'frame_map': 'video_frames.jsonl', 'actor_rows': 'native-actors.jsonl',
               'map': 'road.xodr', 'trace': 'trace.jsonl',
               'source_kind': 'original_carla_capture',
               'control_content_verified': False,
               'employee_exception_verified': False,
               'physical_completion_claimed': False}
    (attempt / 'capture-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'source': 'live_carla_synchronous_20hz',
        'physical_acceptance_claimed': False}, indent=2) + '\n')
    return receipt
