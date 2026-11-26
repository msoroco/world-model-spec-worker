"""Proposed original Native right-pass acquisition; --check is CPU only."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from geometry import (LEAD_LEFT_LANE_Y_M, LEAD_RIGHT_LANE_Y_M, EGO_PAVED_PASS_Y_M,
                      EGO_SHOULDER_PASS_Y_M, PAVED_RIGHT_EDGE_Y_M, check as geometry_check,
                      open_drive)
from necessity import check as necessity_check

FRAMES = 600
RATE_HZ = 20
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
ASSIGNMENT = 'training__C146314__NRS-484B-210-3__motor_vehicle_driver'
ROUTES = {'probe_a': (LEAD_LEFT_LANE_Y_M, EGO_PAVED_PASS_Y_M),
          'probe_b': (LEAD_RIGHT_LANE_Y_M, EGO_SHOULDER_PASS_Y_M)}


def check():
    geometry = geometry_check()
    necessity = necessity_check()
    if FRAMES / RATE_HZ != 30 or len(CAMERAS) != 4 or set(ROUTES) != {'probe_a', 'probe_b'}:
        raise ValueError('Exact right-pass capture duration or routes changed')
    return {'passed': True, 'geometry': geometry, 'necessity': necessity,
            'camera_names': [c[0] for c in CAMERAS], 'frames': FRAMES,
            'native_imported': False, 'physical_pass_observed': False}


def _actor_row(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    corners = actor.bounding_box.get_world_vertices(transform)
    return {'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'center_xyz_m': [transform.location.x, transform.location.y, transform.location.z],
            'body_xy_m': [[point.x, point.y] for point in corners],
            'velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'speed_mps': math.hypot(velocity.x, velocity.y)}


def _camera_pose(carla, name):
    if name == 'driver_reference':
        return carla.Transform(carla.Location(x=.7, y=0, z=1.4),
                               carla.Rotation(pitch=-8)), True
    poses = {'overview': (130, -28, 45, -55),
             'approach': (55, -19, 12, -20),
             'reference_corner': (170, -18, 12, -20)}
    x, y, z, pitch = poses[name]
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch)), False


def execute(case_id, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    if not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('Wrong exact assignment')
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in ROUTES:
        raise ValueError('Unknown exact right-pass case')
    check()
    output = Path(output_dir).resolve()
    if any((output / name).exists() for name in
           ('video_frames.jsonl', 'native_motion.jsonl', 'road.xodr', 'capture-seal.json')):
        raise ValueError('Retain prior Native sources; use a fresh attempt')
    output.mkdir(parents=True, exist_ok=True)
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old_world = client.get_world()
    if saved['settings'].synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for actor in old_world.get_actors()):
        raise RuntimeError('Requires an exclusive idle asynchronous Native world')
    owned, encoders, camera_queues = [], {}, {}
    capture = None
    changed = complete = False
    lead_y, ego_y = ROUTES[suffix]
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=50, wall_height=0, additional_width=0,
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
        mapping = world.get_map()
        for station, lane_id in ((20, -2 if suffix == 'probe_a' else -3),
                                 (60, -1 if suffix == 'probe_a' else -2), (300, -2)):
            if mapping.get_waypoint_xodr(1, lane_id, station) is None:
                raise RuntimeError('Native route lane readback unavailable')
        (output / 'road.xodr').write_text(mapping.to_opendrive())
        road_hash = hashlib.sha256((output / 'road.xodr').read_bytes()).hexdigest()
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        blueprints = world.get_blueprint_library()
        ego_bp = blueprints.find('vehicle.tesla.model3')
        lead_bp = blueprints.find('vehicle.tesla.model3')
        ego_bp.set_attribute('role_name', 'c146314_right_pass_ego')
        lead_bp.set_attribute('role_name', 'c146314_overtaken_vehicle')
        ego = world.try_spawn_actor(ego_bp, carla.Transform(
            carla.Location(x=20, y=ego_y, z=1), carla.Rotation(yaw=0)))
        lead = world.try_spawn_actor(lead_bp, carla.Transform(
            carla.Location(x=60, y=lead_y, z=1), carla.Rotation(yaw=0)))
        if ego is None or lead is None or ego.id == lead.id:
            raise RuntimeError('Original ego/lead vehicles did not separately spawn')
        owned.extend((ego, lead))
        capture = PipelineCapture(client, ego, output, case_id,
                                  required_observations=[])
        for name, width, height in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('sensor_tick', '.05')
            bp.set_attribute('fov', '85')
            pose, attached = _camera_pose(carla, name)
            camera = world.spawn_actor(bp, pose, attach_to=ego if attached else None)
            owned.append(camera)
            frames = queue.Queue()
            camera.listen(frames.put)
            camera_queues[name] = frames
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                '-s', f'{width}x{height}', '-r', str(RATE_HZ), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native_motion.jsonl').open('x') as motion, \
                (output / 'trace.jsonl').open('x') as trace:
            start_time = None
            for index in range(FRAMES):
                ego.set_target_velocity(carla.Vector3D(x=8, y=0, z=0))
                lead.set_target_velocity(carla.Vector3D(x=5, y=0, z=0))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('Original Native snapshot frame differs')
                if start_time is None:
                    start_time = snap.timestamp.elapsed_seconds
                elapsed = snap.timestamp.elapsed_seconds - start_time
                capture.capture(frame, elapsed)
                ego_row, lead_row = _actor_row(ego), _actor_row(lead)
                joined = {}
                for name, frames in camera_queues.items():
                    image = frames.get(timeout=30)
                    while image.frame < frame:
                        image = frames.get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera frame join differs: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    joined[name] = frame
                frame_map.append(frame, elapsed, camera_native_frames=joined)
                motion.write(json.dumps({'video_frame': index, 'native_frame': frame,
                    'time_s': elapsed, 'source_kind': 'original_native_pass',
                    'case_id': case_id, 'ego': ego_row, 'lead': lead_row,
                    'paved_right_edge_y_m': PAVED_RIGHT_EDGE_Y_M,
                    'native_map_sha256': road_hash}) + '\n')
                trace.write(json.dumps({'frame': frame, 'time_s': elapsed,
                    'position_m': ego_row['center_xyz_m'], 'heading_deg': 0,
                    'speed_mps': ego_row['speed_mps'],
                    'speed_mph': ego_row['speed_mps'] / .44704}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + stderr.decode()[-400:])
        (output / 'pass-context.template.json').write_text(json.dumps({
            'case_id': case_id, 'review_kind': 'original_source_review',
            'road_sha256': road_hash, 'paved_right_edge_y_m': PAVED_RIGHT_EDGE_Y_M,
            'lead_y_plan_m': lead_y, 'ego_y_plan_m': ego_y,
            'shoulder_material_requires_original_review': True,
            'native_vehicle_bounding_boxes_require_original_review': True,
            'actual_pixels_reviewed': False}, indent=2) + '\n')
        complete = True
        return {'case_id': case_id, 'frames': FRAMES, 'camera_names': list(camera_queues),
                'physical_acceptance_claimed': False}
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
        restoration = restore(client, saved) if changed else {'restored': True, 'world_unchanged': True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                         encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                         context={'case_id': case_id, 'candidate_id': 'primary',
                                  'pavement_material_review': 'pending_original_source'})


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
        config = json.loads((Path(__file__).parent / 'config.json').read_text())
        case_id = args.case_id or config.get('selected_case_id')
        if case_id != config.get('selected_case_id'):
            raise ValueError('Native case differs from exact materialized bundle')
        print(json.dumps(execute(case_id, args.output_dir, args.host, args.port)))
    else:
        parser.error('Supply --check or exact --case-id and --output-dir')
