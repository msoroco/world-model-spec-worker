"""Proposed original Native bicycle pass capture; CPU --check never imports CARLA."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive

FRAMES = 600
CAMERAS = (('overview', 1920, 1080, -10, -16, 20),
           ('approach', 1280, 720, -32, -9, 5),
           ('reference_corner', 1280, 720, -5, -9, 5),
           ('driver_reference', 1280, 720, 25, -9, 5))


def check():
    geometry = geometry_check()
    if len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('Four original camera streams required')
    if FRAMES / 20 < 30:
        raise ValueError('Full pass capture must last at least 30 seconds')
    return {'passed': True, 'cell_id': 'C146108', 'law_id': 'NRS-484B-270-7b',
            'selected_statutory_subject': 'bicycle', 'frozen_witness_electric_bicycle_still_pending': True,
            'geometry': geometry, 'camera_names': [c[0] for c in CAMERAS],
            'frames': FRAMES, 'native_imported': False, 'physical_acceptance_claimed': False}


def actor_row(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    body = sorted({(round(point.x, 5), round(point.y, 5)) for point in vertices})
    if len(body) != 4:
        raise RuntimeError('Original actor body did not yield four ground corners')
    return {'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'center_xy_m': [transform.location.x, transform.location.y],
            'body_xy_m': [list(point) for point in body],
            'speed_mps': math.hypot(velocity.x, velocity.y)}


def execute(output, host, port, case_id=None):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.media import compose_four_views
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    check()
    if not case_id:
        raise ValueError('Selected bicycle case identity required')
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Use a fresh original Native attempt directory')
    output.mkdir(parents=True)
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('Requires an exclusive idle asynchronous Native world')
    owned, encoders, camera_queues = [], {}, {}
    changed = False
    complete = False
    capture = None
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=50, wall_height=0, additional_width=0,
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
        mapping = world.get_map()
        for x, y, lane_id in ((-50, -1.75, -1), (-30, -5.25, -2)):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=1), project_to_road=True,
                                      lane_type=carla.LaneType.Driving)
            if wp is None or wp.lane_id != lane_id:
                raise RuntimeError('Native one-way lane readback differs')
        blueprints = world.get_blueprint_library()
        bicycle_bp = blueprints.find('vehicle.bh.crossbike')
        motor_bp = blueprints.find('vehicle.tesla.model3')
        bicycle_bp.set_attribute('role_name', 'c146108_bicycle_subject')
        motor_bp.set_attribute('role_name', 'c146108_passed_motor_vehicle')
        bicycle = world.spawn_actor(bicycle_bp, carla.Transform(
            carla.Location(x=-50, y=-1.75, z=1), carla.Rotation(yaw=0)))
        motor = world.spawn_actor(motor_bp, carla.Transform(
            carla.Location(x=-30, y=-5.25, z=1), carla.Rotation(yaw=0)))
        owned.extend((bicycle, motor))
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'rider_model': 'bicycle geometry and Native actor source'}, indent=2) + '\n')
        capture = PipelineCapture(client, bicycle, output, case_id,
                                  visibility=False, required_observations=[])
        for name, width, height, x, y, z in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', '.05')
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                        carla.Rotation(pitch=-25 if z < 10 else -50))
            camera = world.spawn_actor(bp, transform)
            owned.append(camera)
            frames = queue.Queue()
            camera.listen(frames.put)
            camera_queues[name] = frames
            video = output / (name + '.mkv')
            process = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}', '-r', '20',
                '-i', '-', '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1', str(video)],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            encoders[name] = process
        frame_map = output / 'video_frames.jsonl'
        poses = output / 'participant-poses.jsonl'
        with FrameMap(frame_map) as map_stream, poses.open('x') as pose_stream, (output / 'trace.jsonl').open('x') as trace_stream:
            first_elapsed = None
            for index in range(FRAMES):
                bicycle.set_target_velocity(carla.Vector3D(x=5, y=0, z=0))
                motor.set_target_velocity(carla.Vector3D(x=3, y=0, z=0))
                native_frame = world.tick()
                snapshot_frame = world.get_snapshot()
                if snapshot_frame.frame != native_frame:
                    raise RuntimeError('Original Native snapshot/frame identity differs')
                native_seconds = snapshot_frame.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = native_seconds
                elapsed = native_seconds - first_elapsed
                capture.capture(native_frame, elapsed)
                original_bicycle = actor_row(bicycle)
                original_motor = actor_row(motor)
                pose_stream.write(json.dumps({'frame': native_frame, 'native_frame': native_frame, 'video_frame': index,
                    'time_s': elapsed, 'rider_xy_m': original_bicycle['center_xy_m'],
                    'motor_xy_m': original_motor['center_xy_m'],
                    'rider_body_xy_m': original_bicycle['body_xy_m'],
                    'motor_body_xy_m': original_motor['body_xy_m'],
                    'rider_speed_mps': original_bicycle['speed_mps'],
                    'motor_speed_mps': original_motor['speed_mps'],
                    'rider_actor_id': original_bicycle['actor_id'],
                    'motor_actor_id': original_motor['actor_id']}) + '\n')
                trace_stream.write(json.dumps({'frame': native_frame, 'time_s': elapsed,
                    'position_m': [*original_bicycle['center_xy_m'], bicycle.get_transform().location.z],
                    'position': {'x': original_bicycle['center_xy_m'][0],
                                 'y': original_bicycle['center_xy_m'][1],
                                 'z': bicycle.get_transform().location.z},
                    'heading_deg': bicycle.get_transform().rotation.yaw,
                    'speed_mps': original_bicycle['speed_mps'],
                    'speed_mph': original_bicycle['speed_mps'] / .44704,
                    'control': {'bicycle_target_speed_mps': 5}}) + '\n')
                mapped = {}
                for name, _, _, _, _, _ in CAMERAS:
                    received = camera_queues[name].get(timeout=30)
                    while received.frame < native_frame:
                        received = camera_queues[name].get(timeout=30)
                    if received.frame != native_frame:
                        raise RuntimeError('Original camera frame join differs')
                    encoders[name].stdin.write(received.raw_data)
                    mapped[name] = received.frame
                map_stream.append(native_frame, elapsed, camera_native_frames=mapped)
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + stderr.decode()[-400:])
        compose_four_views({name: output / (name + '.mkv') for name in camera_queues},
                           frame_map, output / 'raw.mkv')
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        rider_extent = bicycle.bounding_box.extent
        motor_extent = motor.bounding_box.extent
        (output / 'pass-context.json').write_text(json.dumps({
            'rider_class': 'bicycle', 'passed_class': 'motor_vehicle',
            'rider_dimensions_m': [2 * rider_extent.x, 2 * rider_extent.y],
            'motor_dimensions_m': [2 * motor_extent.x, 2 * motor_extent.y],
            'motor_occupant_count': 1, 'occupant_count_source': 'driver actor only; cabin occupancy unverified',
            'native_classification_review_pending': True}) + '\n')
        complete = True
        return {'frames': FRAMES, 'camera_names': list(camera_queues),
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
                actor.stop() if hasattr(actor, 'stop') else None
                actor.destroy()
            except Exception:
                pass
        restoration = restore(client, saved) if changed else {'restored': True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                         encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                         context={'case_id': case_id, 'physical_review': 'pending_original_source'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check and args.execute:
        raise SystemExit('Choose exactly one of --check or --execute')
    if not args.check and not args.execute and not args.output_dir:
        raise SystemExit('Provide --check or an execution output directory')
    if args.check:
        print(json.dumps(check()))
    else:
        if args.output_dir is None or args.host is None or args.port is None:
            raise SystemExit('Native execution requires output directory, host and port')
        config = json.loads((Path(__file__).resolve().parent / 'config.json').read_text())
        print(json.dumps(execute(args.output_dir, args.host, args.port, config['case_id'])))
