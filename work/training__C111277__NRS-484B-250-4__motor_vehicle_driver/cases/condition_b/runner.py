"""Survey-gated 600-frame Native capture for the selected crosswalk pair.

`--check` is CPU only. Execution requires an exclusively owned CARLA world.
It aborts if OpenDRIVE does not instantiate the governing traffic light.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from controller import InoperativeSignalController, Observation
from scene import (EGO_LANE_Y, FRAMES, INTERSECTION_ENTRY_X, NEAR_CROSSWALK_X,
                   OTHER_LANE_X, RATE_HZ, check as scene_check, road_xml)

ASSIGNMENT = 'training__C111277__NRS-484B-250-4__motor_vehicle_driver'
CASES = {'condition_a': 'halt', 'condition_b': 'roll'}
CAMERAS = (
    ('overview', 1920, 1080, 0, -28, 28, -55, 85),
    ('approach', 1280, 720, -30, -15, 12, -25, 80),
    ('reference_corner', 1280, 720, -12, -9, 8, -35, 75),
    ('driver_reference', 1280, 720, -7, 0, 2, 0, 90),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    scene = scene_check()
    if FRAMES != 600 or RATE_HZ != 20 or len(CAMERAS) != 4:
        raise ValueError('exact recording duration or camera count differs')
    if [camera[0] for camera in CAMERAS] != [
            'overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('camera source names differ')
    return {'passed': True, 'scene': scene, 'cameras': [camera[:3] for camera in CAMERAS],
            'native_executed': False, 'physical_qualification_claimed': False}


def survey(world, carla):
    mapping = world.get_map()
    ego = mapping.get_waypoint(carla.Location(x=-35, y=EGO_LANE_Y, z=1),
                               project_to_road=True, lane_type=carla.LaneType.Driving)
    other = mapping.get_waypoint(carla.Location(x=OTHER_LANE_X, y=-35, z=1),
                                 project_to_road=True, lane_type=carla.LaneType.Driving)
    if ego is None or ego.road_id != 1 or ego.lane_id != -1:
        raise RuntimeError('ego incoming lane Native survey failed')
    if other is None or other.road_id != 3 or other.lane_id != -1:
        raise RuntimeError('conflicting incoming lane Native survey failed')
    xml = mapping.to_opendrive()
    if '<object ' not in xml or 'near-side-crosswalk' not in xml:
        raise RuntimeError('Native map lacks authored crosswalk')
    if 'ego-vehicular-head' not in xml:
        raise RuntimeError('Native map lacks installed signal specification')
    signals = list(world.get_actors().filter('traffic.traffic_light*'))
    candidate = [light for light in signals if
                 abs(light.get_transform().location.x + 16) < 8 and
                 abs(light.get_transform().location.y + 4.2) < 8]
    if len(candidate) != 1:
        raise RuntimeError('exact governing physical traffic-light actor unavailable')
    light = candidate[0]
    affected = light.get_affected_lane_waypoints()
    governs = any(waypoint.road_id == 1 and waypoint.lane_id == -1
                  for waypoint in affected)
    if not governs:
        raise RuntimeError('physical light does not govern ego incoming lane')
    # State Off plus freeze is an engineering fault construction; original pixels
    # and the actor's governed lane must still be checked independently.
    light.set_state(carla.TrafficLightState.Off)
    light.freeze(True)
    if light.get_state() != carla.TrafficLightState.Off or not light.is_frozen():
        raise RuntimeError('Native inoperative state readback failed')
    return light, {'ego_lane': [ego.road_id, ego.lane_id],
                   'other_lane': [other.road_id, other.lane_id],
                   'signal_actor_id': light.id, 'signal_state': 'Off',
                   'signal_pixels_verified': False,
                   'signal_governs_ego_lane_verified': governs,
                   'affected_lanes': [[waypoint.road_id, waypoint.lane_id]
                                      for waypoint in affected]}


def execute(case_id, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check()
    suffix = case_id.rsplit('__', 1)[-1]
    if not case_id.startswith(ASSIGNMENT + '__') or suffix not in CASES:
        raise ValueError('unknown exact selected case')
    condition = CASES[suffix]
    output = Path(output_dir).resolve()
    tuning = json.loads((output / 'config.json').read_text()).get('motion_tuning', {})
    roll_throttle = float(tuning.get('roll_throttle', .22))
    other_entry_speed = float(tuning.get('other_entry_speed_mps', 6.25))
    other_clear_speed = float(tuning.get('other_clear_speed_mps', 4.0))
    if not (0.1 <= roll_throttle <= .4 and 2 <= other_entry_speed <= 8 and
            2 <= other_clear_speed <= 6):
        raise ValueError('fallback motion tuning outside predeclared engineering range')
    if not output.is_dir() or any((output / name).exists() for name in
                                  ('native-rows.jsonl', 'video_frames.jsonl',
                                   'native-index.json')):
        raise ValueError('materialized attempt must have fresh original sources')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    original_world = client.get_world()
    if saved['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in original_world.get_actors()):
        raise RuntimeError('exclusive idle asynchronous Native world required')
    actors, encoders, cameras = [], {}, {}
    capture = None
    restoration = None
    world_changed = False
    try:
        world = client.generate_opendrive_world(
            road_xml(), carla.OpendriveGenerationParameters(
                vertex_distance=.5, max_road_length=25, wall_height=0,
                additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        world_changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        light, surveyed = survey(world, carla)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'native-survey.json').write_text(json.dumps(surveyed, indent=2) + '\n')
        (output / 'signal_context.json').write_text(json.dumps({
            'intersection_polygon_xy_m': [[-7, -7], [7, -7], [7, 7], [-7, 7]],
            'crosswalk_near_edge_x_m': NEAR_CROSSWALK_X,
            'signal_actor_id': light.id,
            'signal_governs_ego_lane_verified': surveyed['signal_governs_ego_lane_verified']},
            indent=2) + '\n')
        library = world.get_blueprint_library()
        blueprint = library.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name', 'c111277_ego')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=-35, y=EGO_LANE_Y, z=1), carla.Rotation(yaw=0)))
        actors.append(ego)
        other_blueprint = library.find('vehicle.audi.tt')
        other_blueprint.set_attribute('role_name', 'c111277_priority_vehicle')
        other = world.spawn_actor(other_blueprint, carla.Transform(
            carla.Location(x=OTHER_LANE_X, y=-35, z=1), carla.Rotation(yaw=90)))
        actors.append(other)
        for name, width, height, x, y, z, pitch, fov in CAMERAS:
            camera_bp = library.find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', str(width))
            camera_bp.set_attribute('image_size_y', str(height))
            camera_bp.set_attribute('fov', str(fov))
            camera_bp.set_attribute('sensor_tick', '.05')
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            actors.append(camera)
            images = queue.Queue()
            camera.listen(images.put)
            cameras[name] = images
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', '20', '-i', '-', '-frames:v', '600', '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        capture = PipelineCapture(client, ego, output, case_id,
                                  visibility=True,
                                  required_observations=json.loads(
                                      (output / 'config.json').read_text())['required_atoms'])
        controller = InoperativeSignalController()
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-rows.jsonl').open('x') as trace, \
                (output / 'interaction_history.jsonl').open('x') as interaction:
            first_time = None
            for index in range(FRAMES):
                ego_pose = ego.get_transform()
                ego_velocity = ego.get_velocity()
                other_pose = other.get_transform()
                other_velocity = other.get_velocity()
                ego_speed = math.sqrt(sum(v * v for v in
                                          (ego_velocity.x, ego_velocity.y, ego_velocity.z)))
                other_speed = math.sqrt(sum(v * v for v in
                                            (other_velocity.x, other_velocity.y, other_velocity.z)))
                ego_front_x = ego_pose.location.x + ego.bounding_box.extent.x
                other_inside = -7 <= other_pose.location.y <= 7
                if condition == 'halt':
                    command = controller.step(Observation(
                        frame=index, signal_installed=True, signal_uncovered=True,
                        signal_inoperative=light.get_state() == carla.TrafficLightState.Off,
                        signal_governs_ego_lane=True, stop_line_present=False,
                        near_crosswalk_present=True,
                        ego_front_distance_to_boundary_m=NEAR_CROSSWALK_X - ego_front_x,
                        ego_speed_mps=ego_speed,
                        prior_stop_vehicle_approaching=(80 <= index < 120),
                        vehicle_in_intersection=other_inside))
                    ego.apply_control(carla.VehicleControl(throttle=command.throttle,
                                                           brake=command.brake))
                else:
                    ego.apply_control(carla.VehicleControl(throttle=roll_throttle, brake=0))
                    command = None
                # Other vehicle stops first, then traverses the junction.
                if index < 80:
                    other.set_target_velocity(carla.Vector3D(x=0, y=other_entry_speed, z=0))
                elif index < 120:
                    other.set_target_velocity(carla.Vector3D(x=0, y=0, z=0))
                elif index < 240:
                    other.set_target_velocity(carla.Vector3D(x=0, y=other_clear_speed, z=0))
                else:
                    other.set_target_velocity(carla.Vector3D(x=0, y=0, z=0))
                frame = world.tick()
                snap = world.get_snapshot()
                if frame != snap.frame:
                    raise RuntimeError('Native frame and snapshot differ')
                # Retain post-tick observations for the frame the cameras depict.
                ego_pose = ego.get_transform()
                ego_velocity = ego.get_velocity()
                other_pose = other.get_transform()
                other_velocity = other.get_velocity()
                ego_speed = math.sqrt(sum(v * v for v in
                                          (ego_velocity.x, ego_velocity.y, ego_velocity.z)))
                other_speed = math.sqrt(sum(v * v for v in
                                            (other_velocity.x, other_velocity.y, other_velocity.z)))
                ego_front_x = ego_pose.location.x + ego.bounding_box.extent.x
                other_inside = -7 <= other_pose.location.y <= 7
                elapsed = snap.timestamp.elapsed_seconds
                if first_time is None:
                    first_time = elapsed
                capture.capture(frame, elapsed - first_time, extra={
                    'c111277_signal_id': light.id,
                    'c111277_signal_state': str(light.get_state()),
                    'c111277_other_actor_id': other.id})
                mapped = {}
                for name, images in cameras.items():
                    image = images.get(timeout=30)
                    while image.frame < frame:
                        image = images.get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('source camera frame join failed: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(frame, elapsed - first_time, camera_native_frames=mapped)
                trace.write(json.dumps({
                    'frame': index, 'time_s': elapsed - first_time,
                    'native_frame': frame, 'ego_actor_id': ego.id,
                    'other_actor_id': other.id, 'signal_actor_id': light.id,
                    'signal_state': str(light.get_state()),
                    'ego_front_x_m': ego_front_x, 'ego_speed_mps': ego_speed,
                    'other_y_m': other_pose.location.y,
                    'other_speed_mps': other_speed,
                    'other_in_intersection': other_inside,
                    'controller_phase': command.phase if command else 'roll',
                    'source_kind': 'original_native_observation'}) + '\n')
                body = [[vertex.x, vertex.y, vertex.z] for vertex in
                        ego.bounding_box.get_world_vertices(ego_pose)]
                interaction.write(json.dumps({
                    'frame': frame, 'time_s': elapsed - first_time,
                    'states': {'ego': {'body_vertices_m': body}},
                    'signal_actor_id': light.id,
                    'signal_state': str(light.get_state()),
                    'other_actor_id': other.id,
                    'other_in_intersection': other_inside}) + '\n')
        capture.close(confirmed=True)
        capture = None
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source camera encoding failed: ' + name + ': ' +
                                   error.decode()[-400:])
        geometry = {'source_kind': 'original_native_survey',
                    'ego_incoming_lane': 'road_1_lane_-1',
                    'stop_line_present': False, 'near_crosswalk_present': True,
                    'crosswalk_near_edge_x_m': NEAR_CROSSWALK_X,
                    'intersection_entry_x_m': INTERSECTION_ENTRY_X,
                    'native_survey': surveyed}
        signal = {'source_kind': 'original_native_observation', 'installed': True,
                  'uncovered': True, 'inoperative_observed': True,
                  'controlled_incoming_lane': 'road_1_lane_-1',
                  'signal_actor_id': light.id,
                  'physical_pixels_verified': False}
        for name, content in (('geometry.json', geometry), ('signal.json', signal)):
            (output / name).write_text(json.dumps(content, indent=2) + '\n')
        names = ('geometry.json', 'signal.json', 'native-rows.jsonl')
        index = {'format': 'nrs-484b-250-4-source-index-v1',
                 'assignment_id': ASSIGNMENT, 'condition': condition,
                 'case_id': case_id, 'rate_hz': RATE_HZ, 'frames': FRAMES,
                 'files': {name: sha(output / name) for name in names}}
        (output / 'native-index.json').write_text(json.dumps(index, indent=2) + '\n')
        result = {'case_id': case_id, 'frames': FRAMES, 'cameras': list(cameras),
                  'physical_signal_pixels_verified': False,
                  'legal_outcome_asserted': False}
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if world_changed:
            restoration = restore(client, saved)
    seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                 encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                 context={'case_id': case_id, 'signal_physical_pixels_verified': False})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case-id')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if not args.check and not args.output_dir:
        raise SystemExit('execution needs --output-dir')
    if args.check:
        print(json.dumps(check()))
    else:
        case_id = args.case_id or json.loads(Path('config.json').read_text())['selected_case_id']
        print(json.dumps(execute(case_id, args.output_dir, args.host, args.port)))
