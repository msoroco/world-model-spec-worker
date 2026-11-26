"""Capture an authored left-turn request with original Native source joins."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from median_scene import CAMERAS, check as check_scene

FRAMES = 600
CAMERA_POSES = {
    'overview': ((0, -19, 25), (0, -52, 90), False),
    'approach': ((1.2, 0, 2.0), (0, -8, 0), True),
    'reference_corner': ((9, -14, 11), (0, -22, 90), False),
    'driver_reference': ((1, 14, 11), (0, -22, -90), False),
}


def check():
    root = Path.cwd()
    config = json.loads((root/'config.json').read_text())
    request = json.loads((root/'request.json').read_text())
    check_scene(request)
    if config['selected_case_id'] != config['case_id'] or config['case_id'].rsplit('__', 1)[-1] != request['case']:
        raise ValueError('Exact median case identity differs')
    if (config['rate_hz'], config['duration_s'], config['frames']) != (20, 30, FRAMES):
        raise ValueError('Capture duration differs')
    if hashlib.sha256((root/'request.json').read_bytes()).hexdigest() != config['request_sha256']:
        raise ValueError('Median request hash differs')
    if (root/'road.xodr').read_text() != request['source_map']:
        raise ValueError('Authored road differs')
    return {'passed': True, 'case_id': config['case_id'], 'frames': FRAMES,
            'physical_native_verified': False, 'authority_verified': False}


def ego_row(actor):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    body = actor.bounding_box.get_world_vertices(pose)
    bottom = sorted(body, key=lambda vertex: vertex.z)[:4]
    bottom.sort(key=lambda vertex: math.atan2(vertex.y-pose.location.y,
                                              vertex.x-pose.location.x))
    return {'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'center_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
            'yaw_deg': pose.rotation.yaw,
            'body_xy_m': [[vertex.x, vertex.y] for vertex in bottom],
            'body_xyz_m': [[vertex.x, vertex.y, vertex.z] for vertex in body],
            'speed_mps': math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
            'velocity_xyz_mps': [velocity.x, velocity.y, velocity.z]}


def control_to_target(actor, target):
    pose = actor.get_transform()
    dx, dy = target[0]-pose.location.x, target[1]-pose.location.y
    distance = math.hypot(dx, dy)
    bearing = math.degrees(math.atan2(dy, dx))
    error = ((bearing-pose.rotation.yaw+180) % 360)-180
    steer = max(-.65, min(.65, error/55))
    return distance, steer


def execute(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap, seal_capture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore
    check()
    output = Path(output).resolve()
    if output != Path.cwd().resolve():
        raise ValueError('Capture requires the fresh materialized exact bundle')
    if any((output/name).exists() for name in ('native-median.jsonl', 'video_frames.jsonl', 'capture-seal.json')):
        raise ValueError('Original acquisition already exists')
    request = json.loads((output/'request.json').read_text())
    config = json.loads((output/'config.json').read_text())
    client = carla.Client(host, port)
    client.set_timeout(180)
    old_world = client.get_world()
    saved = snapshot(client)
    if old_world.get_settings().synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in old_world.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned = []
    encoders = {}
    cameras = {}
    capture = None
    changed = False
    restoration = None
    try:
        world = client.generate_opendrive_world((output/'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        map_source = world.get_map().to_opendrive()
        roadways = []
        for road_id in (1241631, 1241632):
            waypoint = world.get_map().get_waypoint_xodr(road_id, -1, 65)
            if waypoint is None or waypoint.lane_type != carla.LaneType.Driving:
                raise RuntimeError('Native divided roadway missing: '+str(road_id))
            roadways.append({'road_id': road_id, 'lane_id': -1,
                             'heading_deg': waypoint.transform.rotation.yaw})
        if abs(((roadways[0]['heading_deg']-roadways[1]['heading_deg']+180) % 360)-180) < 150:
            raise RuntimeError('Native roadways are not opposing directions')
        objects = [dict(item.attrib) for item in ET.fromstring(map_source).findall('.//object')
                   if item.get('name', '').startswith('median_dividing_section_')]
        if len(objects) != 2:
            raise RuntimeError('Native median objects not retained')
        blueprints = world.get_blueprint_library()
        blueprint = blueprints.find(request['ego_blueprint'])
        blueprint.set_attribute('role_name', 'c124163_median_subject')
        start = request['start_xyz_m']
        ego = world.try_spawn_actor(blueprint, carla.Transform(
            carla.Location(x=start[0], y=start[1], z=config['spawn_z_m']),
            carla.Rotation(yaw=0)))
        if ego is None:
            raise RuntimeError('Original median subject spawn failed')
        owned.append(ego)
        for name, width, height in CAMERAS:
            point, angles, attach = CAMERA_POSES[name]
            camera_bp = blueprints.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 85), ('sensor_tick', .05)):
                camera_bp.set_attribute(key, str(value))
            pose = carla.Transform(carla.Location(x=point[0], y=point[1], z=point[2]),
                                   carla.Rotation(roll=angles[0], pitch=angles[1], yaw=angles[2]))
            sensor = (world.spawn_actor(camera_bp, pose, attach_to=ego)
                      if attach else world.spawn_actor(camera_bp, pose))
            owned.append(sensor)
            image_queue = queue.Queue()
            sensor.listen(image_queue.put)
            cameras[name] = image_queue
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                '-s', f'{width}x{height}', '-r', '20', '-i', '-', '-frames:v', '600',
                '-c:v', 'ffv1', str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        capture = PipelineCapture(client, ego, output, config['selected_case_id'],
                                  required_observations=())
        targets = request['route_waypoints_xy_m'][1:]
        target_index = 0
        with (output/'native-median.jsonl').open('x') as motion, \
                (output/'body_history.jsonl').open('x') as body_history, \
                FrameMap(output/'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                distance, steer = control_to_target(ego, targets[target_index])
                if distance < 2.0 and target_index < len(targets)-1:
                    target_index += 1
                    distance, steer = control_to_target(ego, targets[target_index])
                done = target_index == len(targets)-1 and distance < 2.0
                ego.apply_control(carla.VehicleControl(throttle=0 if done else .28,
                    brake=1 if done else 0, steer=0 if done else steer))
                native_frame = world.tick()
                capture.capture(native_frame, index/20)
                ego_source = ego_row(ego)
                motion.write(json.dumps({'native_frame': native_frame,
                    'video_frame': index, 'time_s': index/20,
                    'source_kind': 'original_native', 'ego': ego_source,
                    'route_target_index': target_index, 'legal_verdict': None},
                    allow_nan=False)+'\n')
                body_history.write(json.dumps({'frame': index, 'time_s': index/20,
                    'body_vertices_m': ego_source['body_xyz_m'],
                    'heading_deg': ego_source['yaw_deg']}, allow_nan=False)+'\n')
                mapped = {}
                for name, image_queue in cameras.items():
                    image = image_queue.get(timeout=30)
                    while image.frame < native_frame:
                        image = image_queue.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera/native frame join differs: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, index/20, camera_native_frames=mapped)
        capture.close()
        capture = None
        for name, encoder in encoders.items():
            encoder.stdin.close()
            stderr = encoder.stderr.read()
            if encoder.wait(timeout=180):
                raise RuntimeError('Camera encode failed: '+name+stderr.decode()[-200:])
        (output/'median-context.json').write_text(json.dumps({
            'source_kind': 'original_native_median_readback',
            'authored_road_ids': [1241631, 1241632],
            'native_map_sha256': hashlib.sha256(map_source.encode()).hexdigest(),
            'native_roadways': roadways, 'median_objects': objects,
            'median_bounds_m': request['median_bounds_m'],
            'opening_bounds_m': request['opening_bounds_m'],
            'barrier_bounds_m': request['barrier_bounds_m'],
            'public_authority_establishment': 'pending_original_source',
            'original_body_and_pixels_reviewed': False,
            'legal_verdict': None}, indent=2)+'\n')
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for encoder in encoders.values():
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restoration = restore(client, saved)
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'physical_acceptance_claimed': False})+'\n')
    seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                 encoder_exit_codes={name: 0 for name in cameras},
                 context={'authored_road_ids': [1241631, 1241632]})
    return {'frames': FRAMES, 'source_review_complete': False,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        if args.output_dir is None:
            parser.error('Native output directory required')
        print(json.dumps(execute(args.output_dir, args.host, args.port)))
