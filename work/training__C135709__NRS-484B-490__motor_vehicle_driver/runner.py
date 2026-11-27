"""Prospective original Native capture of two narrow-highway parking locations."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import queue
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from geometry import DEVICE_ID, DEVICE_NAME, GOVERNED_X_M, PARK_X_M, PARK_Y_M, check as geometry_check, open_drive

ASSIGNMENT = 'training__C135709__NRS-484B-490__motor_vehicle_driver'
FRAMES = 600
RATE_HZ = 20
CAMERAS = (
    ('overview', 1920, 1080, 0, -16, 15, -38),
    ('approach', 1280, 720, -22, -10, 7, -15),
    ('reference_corner', 1280, 720, 10, -12, 6, -18),
    ('driver_reference', 1280, 720, 42, -12, 7, -20),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config.get('case_id') in {ASSIGNMENT + '__' + x for x in PARK_X_M},
            'Unknown exact narrow-highway parking case')
    require((config.get('law_id'), config.get('cell_id'), config.get('actor')) ==
            ('NRS-484B-490', 'C135709', 'motor_vehicle_driver'),
            'Wrong law, cell or actor')
    require(config.get('frozen_cell') ==
            {'layout': 'narrow_road', 'maneuver': 'park', 'control': 'parking_restriction_device'},
            'Wrong frozen cell')
    suffix = config['case_id'].split('__')[-1]
    require(config.get('parking_x_m') == PARK_X_M[suffix] and
            config.get('parking_y_m') == PARK_Y_M,
            'Controlled parking position changed')
    require(config.get('duration_s') == 30 and config.get('rate_hz') == RATE_HZ and
            config.get('duration_frames') == FRAMES, '30-second 20-Hz capture required')
    cameras = config.get('cameras')
    require(isinstance(cameras, list) and len(cameras) == 4 and
            [(c.get('name'), c.get('width'), c.get('height')) for c in cameras] ==
            [(name, width, height) for name, width, height, *_ in CAMERAS],
            'Four source cameras changed')
    require(all(c.get('pose_strategy') and c.get('fov_deg') and c.get('fps') == RATE_HZ
                for c in cameras), 'Camera pose or cadence missing')
    require(config.get('physical_verified') is False and config.get('legal_verdict') is None,
            'Requested parking position cannot establish physical or legal result')
    return {'geometry': geometry_check(), 'case_id': config['case_id'],
            'frames': FRAMES, 'physical_verified': False}


def _readback(world):
    root = ET.fromstring(world.get_map().to_opendrive())
    signs = [s for s in root.findall('.//signal') if s.attrib.get('id') == DEVICE_ID]
    require(len(signs) == 1 and signs[0].attrib.get('name') == DEVICE_NAME,
            'Native prohibitory-device readback failed')
    lanes = root.findall('road/lanes/laneSection/left/lane') + root.findall('road/lanes/laneSection/right/lane')
    require([(x.attrib.get('id'), x.attrib.get('type')) for x in lanes] ==
            [('1', 'driving'), ('-1', 'driving')], 'Native narrow-road lane readback failed')
    return {'sign': dict(signs[0].attrib),
            'lanes': [{'id': x.attrib['id'], 'width_m': float(x.find('width').attrib['a'])} for x in lanes],
            'official_authority_verified': False, 'legal_narrowness_verified': False,
            'governed_extent_verified': False, 'sign_pixels_verified': False}


def validate_source_review(review, config):
    require(review.get('source_kind') == 'original_scene_setup' and
            review.get('case_id') == config['case_id'], 'Exact original scene review required')
    refs = review.get('sources')
    require(isinstance(refs, dict) and set(refs) ==
            {'highway', 'narrow_designation', 'official_authority', 'device_erection', 'governed_extent'},
            'Original road, authority, erection, and extent sources required')
    for name, ref in refs.items():
        source = Path(ref['path'])
        require(source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() ==
                ref.get('sha256'), 'Original source changed: ' + name)
    require(review.get('governed_extent_xyxy_m') and review.get('map_name') and
            review.get('device_id') == DEVICE_ID and
            review.get('physical_verified') is False and
            review.get('legal_verdict') is None,
            'Prospective review cannot claim authority or physical result')
    return review


def execute(config, output_dir, source_review, host, port):
    check(config)
    review = (validate_source_review(json.loads(Path(source_review).read_text()), config)
              if source_review else None)
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output_dir).resolve()
    require(not any((output / name).exists() for name in ('road.xodr', 'vehicle-pose.jsonl', 'video_frames.jsonl')),
            'Choose a fresh original Native attempt directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    previous = client.get_world()
    require(not saved['settings'].synchronous_mode and not any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in previous.get_actors()),
            'Exclusive idle asynchronous Native world required')
    owned, encoders, image_queues = [], {}, {}
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        survey = _readback(world)
        output.mkdir(parents=True, exist_ok=True)
        source_map = world.get_map().to_opendrive().encode()
        (output / 'road.xodr').write_bytes(source_map)
        (output / 'road-context.json').write_text(json.dumps({
            'assignment_id': ASSIGNMENT, 'case_id': config['case_id'],
            'source_kind': 'native_saved_sample',
            'map_sha256': hashlib.sha256(source_map).hexdigest(),
            'map_name': world.get_map().name, 'native_survey': survey,
            'requested_governed_extent_xyxy_m':
                (review['governed_extent_xyxy_m'] if review else
                 [GOVERNED_X_M[0], -3.1, GOVERNED_X_M[1], 0]),
            'requested_parking_xy_m': [config['parking_x_m'], config['parking_y_m']],
            'original_source_refs': review['sources'] if review else None,
            'official_authority_verified': False, 'narrow_highway_verified': False,
            'governed_extent_verified': False, 'physical_verified': False,
            'legal_verdict': None}, indent=2) + '\n')
        blueprints = world.get_blueprint_library()
        vehicle_bp = blueprints.find('vehicle.tesla.model3')
        vehicle_bp.set_attribute('role_name', 'c135709_parking_subject')
        vehicle = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=config['parking_x_m'], y=config['parking_y_m'], z=1),
            carla.Rotation(yaw=0)))
        owned.append(vehicle)
        for name, width, height, x, y, z, pitch in CAMERAS:
            camera_bp = blueprints.find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', str(width))
            camera_bp.set_attribute('image_size_y', str(height))
            camera_bp.set_attribute('fov', '85')
            camera_bp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            image_queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', str(RATE_HZ), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (output / 'vehicle-pose.jsonl').open('x') as poses:
            first_elapsed = None
            for index in range(FRAMES):
                vehicle.apply_control(carla.VehicleControl(throttle=0, brake=1, hand_brake=True))
                native_frame = world.tick()
                snapshot_now = world.get_snapshot()
                require(snapshot_now.frame == native_frame, 'Native frame identity changed')
                elapsed = snapshot_now.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = elapsed
                relative = elapsed - first_elapsed
                transform, velocity = vehicle.get_transform(), vehicle.get_velocity()
                extent = vehicle.bounding_box.extent
                x, y = transform.location.x, transform.location.y
                yaw = math.radians(transform.rotation.yaw)
                co, si = math.cos(yaw), math.sin(yaw)
                corners = [[x + dx * co - dy * si, y + dx * si + dy * co]
                           for dx, dy in ((-extent.x, -extent.y), (extent.x, -extent.y),
                                          (extent.x, extent.y), (-extent.x, extent.y))]
                camera_frames = {}
                for name, q in image_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    require(image.frame == native_frame, 'Original camera frame join failed: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, relative, camera_native_frames=camera_frames)
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': relative, 'vehicle_id': str(vehicle.id),
                    'speed_mps': velocity.length(), 'x_m': x, 'y_m': y,
                    'bbox_half_length_m': extent.x, 'bbox_half_width_m': extent.y,
                    'footprint_corners_xy_m': corners, 'camera_native_frames': camera_frames}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            require(process.wait(timeout=180) == 0 and (output / (name + '.mkv')).is_file(),
                    'Original camera encoding failed: ' + name + ': ' + stderr.decode()[-400:])
        return {'frames': FRAMES, 'case_id': config['case_id'], 'native_survey': survey,
                'source_review_required': True, 'physical_verified': False,
                'legal_verdict': None}
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(Path(__file__).with_name('config.json')))
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--source-review')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    configuration = json.loads(Path(args.config).read_text())
    if args.check:
        print(json.dumps(check(configuration)))
    else:
        require(args.output_dir, '--output-dir required for Native capture')
        print(json.dumps(execute(configuration, args.output_dir, args.source_review,
                                 args.host, args.port)))
