"""Prospective Native four-view capture of six roadway-edge rest requests."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from cameras import transform
from activity import spawn as spawn_passenger, control as control_passenger
from roadside_scene import check


HERE = Path(__file__).resolve().parent


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def speed(actor):
    v = actor.get_velocity()
    value = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if not math.isfinite(value):
        raise ValueError('Nonfinite Native velocity')
    return value


def capture(config, output_dir, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    road = (HERE / 'road-edge-road.xodr').read_text()
    scene = check(config, road)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use a fresh exact-case materialized output')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old_world = client.get_world()
    if old_world.get_settings().synchronous_mode or [actor for actor in old_world.get_actors()
            if actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))]:
        raise RuntimeError('Exclusive idle asynchronous world ownership required')
    actors, encoders, logs, queues = [], {}, {}, {}
    pipeline = None
    world_changed = False
    frames = 0
    error = None
    restored = None
    try:
        world = client.generate_opendrive_world(road,
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        world_changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        native_map = world.get_map()
        location = carla.Location(x=scene['requested_center_x_m'], y=0, z=1)
        lane = native_map.get_waypoint(location, project_to_road=False,
                                       lane_type=carla.LaneType.Driving)
        sidewalk = native_map.get_waypoint(carla.Location(x=7.8, y=0, z=1),
                                           project_to_road=False, lane_type=carla.LaneType.Sidewalk)
        if lane is None or sidewalk is None or lane.road_id != sidewalk.road_id or \
                lane.lane_id == sidewalk.lane_id:
            raise RuntimeError('Original roadway edge or outside sidewalk not present')
        map_sha = sha_bytes(native_map.to_opendrive().encode())
        survey = {'source_kind': 'original_native_road_edge_survey',
            'fixed_cell': {'layout': 'road', 'maneuver': 'parallel_park', 'control': 'road_edge'},
            'map_name': native_map.name, 'roadway_boundary_source_id': 'native-road-1-edge-7m',
            'edge_tangent_source_id': 'native-road-1-planview',
            'lawful_traffic_source_id': 'native-road-1-driving-lane-direction',
            'parking_permission_source_id': 'not-established-original-review-pending',
            'roadway_class_source_id': 'native-road-1-lane-type',
            'vehicle_identity_source_id': 'original-native-actor-id',
            'driver_identity_source_id': 'operator-review-pending',
            'rest_activity_source_id': 'original-video-review-pending',
            'reviewed_source_sha256': map_sha, 'reviewer': 'original-native-readback-pending-independent-review',
            'chapter_exception_status': 'unknown', 'chapter_exception_source_refs': [],
            'edge_tangent_xy': [0, 1], 'lawful_direction_xy': [0, 1],
            'spawn_xyz_yaw_deg': [scene['requested_center_x_m'], 0, .5, scene['requested_yaw_deg']],
            'rest_xyz_m': [scene['requested_center_x_m'], 0, .5],
            'vehicle_blueprint': 'vehicle.lincoln.mkz_2020',
            'authority_and_activity_independently_verified': False}
        write_new(output / 'road_edge_survey.json', survey)
        survey_sha = sha_bytes((output / 'road_edge_survey.json').read_bytes())
        geometry = {'source_kind': 'original_native_road_geometry',
            'survey_sha256': survey_sha, 'authored_map_sha256': sha_bytes(road.encode()),
            'native_map_sha256': map_sha, 'native_road_id': lane.road_id,
            'driving_lane_id': lane.lane_id, 'outside_sidewalk_lane_id': sidewalk.lane_id,
            'roadway_boundary_source_id': survey['roadway_boundary_source_id'],
            'lawful_traffic_source_id': survey['lawful_traffic_source_id'],
            'roadway_class': 'roadway', 'road_edge_identified': True,
            'edge_tangent_xy': survey['edge_tangent_xy'],
            'lawful_traffic_direction_xy': survey['lawful_direction_xy'],
            'edge_x_m': 7, 'native_body_containment_review_required': True,
            'original_native_observed': True}
        write_new(output / 'road_geometry.json', geometry)
        blueprint = world.get_blueprint_library().find(survey['vehicle_blueprint'])
        blueprint.set_attribute('role_name', 'c229351_ego')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=scene['requested_center_x_m'], y=0, z=.5),
            carla.Rotation(yaw=scene['requested_yaw_deg'])))
        if ego is None:
            raise RuntimeError('Original motor vehicle failed to spawn')
        actors.append(ego)
        passenger = spawn_passenger(config, world, carla)
        if passenger is not None:
            actors.append(passenger)
        hand_brake = config['controller_mode'] == 'service_and_hand_brake'
        write_new(output / 'activity_context.json', {
            'case_id': config['case_id'], 'activity_requested': config['activity_requested'],
            'controller_mode': config['controller_mode'],
            'actual_standing_or_parking_review_required': True,
            'driver_and_passenger_purpose_review_required': True,
            'chapter_exception_review_required': True,
            'legal_result': None})
        for item in config['cameras']:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for name, value in (('image_size_x', item['width']),
                                ('image_size_y', item['height']),
                                ('fov', item['fov_deg']), ('sensor_tick', 0)):
                bp.set_attribute(name, str(value))
            sensor = world.spawn_actor(bp, transform(carla, item),
                attach_to=ego if item['pose_strategy'] == 'ego_follow' else None)
            actors.append(sensor)
            queues[item['name']] = queue.Queue()
            sensor.listen(queues[item['name']].put)
            logs[item['name']] = (output / (item['name'] + '.encoder.log')).open('x')
            encoders[item['name']] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f"{item['width']}x{item['height']}", '-r', '20', '-i', 'pipe:0',
                '-an', '-c:v', 'ffv1', str(output / (item['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=logs[item['name']])
        pipeline = PipelineCapture(client, ego, output, config['case_id'],
            visibility=False, required_observations=config.get('required_atoms', []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native_samples.jsonl').open('x') as samples, \
             (output / 'body_history.jsonl').open('x') as bodies, \
             FrameMap(output / 'video_frames.jsonl') as frame_map:
            for index in range(config['duration_frames']):
                ego.apply_control(carla.VehicleControl(brake=1, hand_brake=hand_brake))
                activity_phase = control_passenger(passenger, index / 20, carla)
                native_frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                native_lane = native_map.get_waypoint(pose.location,
                    project_to_road=False, lane_type=carla.LaneType.Driving)
                row = {'source_kind': 'original_native', 'case_id': config['case_id'],
                    'native_frame': native_frame, 'time_s': elapsed,
                    'ego_center_xy_m': [pose.location.x, pose.location.y],
                    'ego_front_yaw_deg': pose.rotation.yaw, 'ego_speed_mps': speed(ego),
                    'native_road_id': None if native_lane is None else native_lane.road_id,
                    'native_lane_id': None if native_lane is None else native_lane.lane_id,
                    'roadway_boundary_source_id': geometry['roadway_boundary_source_id'],
                    'lawful_traffic_source_id': geometry['lawful_traffic_source_id'],
                    'requested_activity': config['activity_requested'],
                    'requested_passenger_phase': activity_phase,
                    'passenger_actor_id': None if passenger is None else passenger.id,
                    'passenger_center_xy_m': None if passenger is None else
                        [passenger.get_location().x, passenger.get_location().y],
                    'original_native_observed': True}
                samples.write(json.dumps(row, allow_nan=False) + '\n')
                pipeline.capture(native_frame, elapsed, extra={'c229351_native': row})
                vertices = ego.bounding_box.get_world_vertices(pose)
                passenger_vertices = None if passenger is None else \
                    passenger.bounding_box.get_world_vertices(passenger.get_transform())
                bodies.write(json.dumps({'native_frame': native_frame, 'time_s': elapsed,
                    'body_vertices_m': [[v.x, v.y, v.z] for v in vertices],
                    'passenger_body_vertices_m': None if passenger_vertices is None else
                        [[v.x, v.y, v.z] for v in passenger_vertices],
                    'native_road_id': row['native_road_id'], 'native_lane_id': row['native_lane_id']},
                    allow_nan=False) + '\n')
                for item in config['cameras']:
                    image = queues[item['name']].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[item['name']].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original four-view camera/Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        item['height'], item['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[item['name']].stdin.write(rgb.tobytes())
                frame_map.append(native_frame, elapsed, all_four_cameras_joined=True)
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if pipeline is not None:
            try:
                pipeline.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(actors):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        if world_changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        write_new(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'frames': frames,
            'expected_frames': config['duration_frames'], 'restoration': restored,
            'error': error, 'accepted': False,
            'required_saved_checks': ['source-hashed Native pose/road geometry',
                'actual standing or parking purpose', 'Chapter exception applicability',
                'roadway body containment and four-view video']})
    if error:
        raise RuntimeError('Native road-edge capture failed; inspect native-capture-report.json')
    return {'case_id': config['case_id'], 'frames': frames,
            'original_native_captured': True, 'activity_verified': False,
            'chapter_exception_verified': False, 'accepted': False}
