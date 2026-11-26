"""Prospective original Native angle-bay capture with separate permission source."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import traceback

from angle_park import check_config
from cameras import check as check_cameras, transform as camera_transform

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(config):
    road = (HERE / 'angle-bay-road.xodr').read_text()
    result = check_config(config, road)
    check_cameras(config['cameras'])
    if config.get('requested_front_yaw_deg') not in (45, 225):
        raise ValueError('Undeclared angle-park orientation request')
    if config.get('parking_brake_mode') not in ('hand_brake', 'service_and_hand_brake'):
        raise ValueError('Undeclared parking control candidate')
    return {**result, 'requested_yaw_deg': config['requested_front_yaw_deg'],
            'permission_evidence_required': True, 'original_native_executed': False}


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
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use a fresh exact-case materialized output')
    permission = os.environ.get('CITY_ENGINEER_PERMISSION_SOURCE')
    if not permission or not Path(permission).is_file():
        raise ValueError('Original City Traffic Engineer permission source file required')
    permission = Path(permission).resolve()
    if not permission.stat().st_size:
        raise ValueError('Empty City Traffic Engineer permission source')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old_world = client.get_world()
    if old_world.get_settings().synchronous_mode or [a for a in old_world.get_actors()
            if a.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))]:
        raise RuntimeError('Exclusive idle asynchronous world ownership required')
    actors, encoders, logs, queues = [], {}, {}, {}
    pipeline = None
    world_changed = False
    frames = 0
    error = None
    restored = None
    try:
        road = (HERE / 'angle-bay-road.xodr').read_text()
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
        lane = native_map.get_waypoint(carla.Location(x=1.75, y=0, z=1),
            project_to_road=False, lane_type=carla.LaneType.Driving)
        bay_lane = native_map.get_waypoint(carla.Location(x=6.5, y=0, z=1),
            project_to_road=False, lane_type=carla.LaneType.Parking)
        if lane is None or bay_lane is None or lane.road_id != bay_lane.road_id or \
                lane.lane_id == bay_lane.lane_id:
            raise RuntimeError('Native one-way driving lane or angle-parking lane survey failed')
        shutil.copyfile(permission, output / 'permission-source.bin')
        write_new(output / 'permission_authority.json', {
            'source_kind': 'original_external_document', 'authority_claim': 'City Traffic Engineer',
            'source_file': 'permission-source.bin', 'source_sha256': sha(output / 'permission-source.bin'),
            'native_road_id': lane.road_id, 'permission_verified': False,
            'independent_authority_and_street_review_required': True,
            'authored_sign_not_permission_evidence': True})
        write_new(output / 'road_geometry.json', {
            'authored_map_sha256': hashlib.sha256(road.encode()).hexdigest(),
            'native_map_sha256': hashlib.sha256(native_map.to_opendrive().encode()).hexdigest(),
            'native_road_id': lane.road_id, 'driving_lane_id': lane.lane_id,
            'parking_lane_id': bay_lane.lane_id, 'lawful_traffic_heading_deg': 90,
            'bay_center_xy_m': [6.5, 0], 'bay_heading_deg': 45,
            'bay_extent_length_m': 6, 'bay_extent_width_m': 3,
            'sign_or_marking_readback_review_required': True,
            'provenance': 'original_native_capture'})
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'c385967_ego')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=6.5, y=0, z=.5),
            carla.Rotation(yaw=config['requested_front_yaw_deg'])))
        actors.append(ego)
        brake = 0 if config['parking_brake_mode'] == 'hand_brake' else 1
        for _ in range(20):
            ego.apply_control(carla.VehicleControl(brake=brake, hand_brake=True))
            world.tick()
        write_new(output / 'parking_context.json', {
            'control': 'angle_parking_designation', 'native_actor_id': ego.id,
            'native_blueprint': ego.type_id, 'native_road_id': bay_lane.road_id,
            'native_parking_lane_id': bay_lane.lane_id,
            'requested_front_yaw_deg': config['requested_front_yaw_deg'],
            'requested_activity': 'standing_or_parked',
            'actual_activity_and_bay_containment_review_required': True,
            'legal_orientation_tolerance_defined': False})
        for item in config['cameras']:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for name, value in [('image_size_x', item['width']), ('image_size_y', item['height']),
                                ('fov', item['fov_deg']), ('sensor_tick', 0)]:
                bp.set_attribute(name, str(value))
            sensor = world.spawn_actor(bp, camera_transform(carla, item),
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
             (output / 'video_frames.jsonl').open('x') as joins, \
             (output / 'body_history.jsonl').open('x') as bodies:
            for index in range(600):
                control = carla.VehicleControl(brake=brake,
                    hand_brake=True)
                ego.apply_control(control)
                native_frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                native_lane = native_map.get_waypoint(pose.location,
                    project_to_road=False, lane_type=carla.LaneType.Parking)
                row = {'source_kind': 'original_native', 'provenance': 'original_native_capture',
                    'case_id': config['case_id'], 'frame': index, 'sample_index': index,
                    'native_frame': native_frame, 'time_s': elapsed,
                    'ego_center_xy_m': [pose.location.x, pose.location.y],
                    'ego_front_yaw_deg': pose.rotation.yaw, 'ego_speed_mps': speed(ego),
                    'native_road_id': None if native_lane is None else native_lane.road_id,
                    'native_lane_id': None if native_lane is None else native_lane.lane_id,
                    'parking_activity_review': {'control_brake': control.brake,
                        'hand_brake': control.hand_brake, 'actual_rest_review_required': True},
                    'permission_document_claimed': False,
                    'original_native_observed': True}
                samples.write(json.dumps(row, allow_nan=False) + '\n')
                pipeline.capture(native_frame, elapsed, extra={'c385967_native': row})
                vertices = ego.bounding_box.get_world_vertices(pose)
                bodies.write(json.dumps({'frame': native_frame, 'time_s': elapsed,
                    'native_road_id': row['native_road_id'], 'native_lane_id': row['native_lane_id'],
                    'body_vertices_m': [[v.x, v.y, v.z] for v in vertices]},
                    allow_nan=False) + '\n')
                for item in config['cameras']:
                    image = queues[item['name']].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[item['name']].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera/Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        item['height'], item['width'], 4)[:, :, :3][:, :, ::-1]
                    encoders[item['name']].stdin.write(rgb.tobytes())
                joins.write(json.dumps({'video_frame': index, 'carla_frame': native_frame,
                    'native_frame': native_frame, 'time_s': elapsed}) + '\n')
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
        write_new(output / 'native-capture-report.json', {'case_id': config['case_id'],
            'frames': frames, 'expected_frames': 600, 'restoration': restored,
            'error': error, 'accepted': False,
            'required_saved_checks': ['original City Traffic Engineer decision and street review',
                'original sign/marking readback', 'parked body pose and activity',
                'four-view video and source-frame joins']})
    if error:
        raise RuntimeError('Native angle-bay capture failed; inspect native-capture-report.json')
    return {'case_id': config['case_id'], 'frames': frames,
            'original_native_captured': True, 'permission_verified': False,
            'accepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not (args.output_dir and args.host and args.port):
            parser.error('Supply --output-dir, --host and --port')
        print(json.dumps(capture(config, args.output_dir, args.host, args.port)))
