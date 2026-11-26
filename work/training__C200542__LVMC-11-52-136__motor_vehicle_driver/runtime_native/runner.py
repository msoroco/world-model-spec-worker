"""Original Native premises parking acquisition; --check is CARLA-free."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from layout import AISLE, BAY, ROUTE, check as layout_check, open_drive

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
MOUNTS = {'overview': (3, -17, 20, -65), 'approach': (-16, -13, 6, -20),
          'reference_corner': (3, -13, 6, -30), 'driver_reference': (3, 7, 10, -45)}


def check():
    geometry = layout_check()
    cfg = json.loads(Path('config.json').read_text())
    if (cfg['cell_id'], cfg['law_id'], cfg['actor']) != ('C200542', 'LVMC-11-52-136', 'motor_vehicle_driver'):
        raise ValueError('Frozen assignment identity differs')
    if cfg['case_suffix'] not in ('controlled_1', 'controlled_2') or cfg['case_id'].rsplit('__', 1)[-1] != cfg['case_suffix']:
        raise ValueError('Exact controlled case differs')
    if cfg['duration_s'] != 30 or cfg['rate_hz'] != 20 or tuple(c['name'] for c in cfg['cameras']) != CAMERAS:
        raise ValueError('Original duration/camera contract differs')
    return {'passed': True, 'case_id': cfg['case_id'], 'geometry': geometry,
            'frames': FRAMES, 'native_imported': False, 'physical_acceptance_claimed': False}


def execute(output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    cfg = json.loads(Path('config.json').read_text())
    check()
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'native-vehicle.jsonl').exists():
        raise ValueError('New materialized attempt required')
    (output / 'law-text.json').write_text(json.dumps({'source': 'LVMC 11.52.136',
        'text': cfg['statutory_text']}, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned, encoders, queues = [], {}, {}
    capture = None
    changed = complete = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=50, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        waypoint = world.get_map().get_waypoint(carla.Location(x=3.5, y=-6, z=1),
            project_to_road=True, lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != -1:
            raise RuntimeError('Native premises drivable-surface readback failed')
        # Diagnostic hatching and route edge aid pixels. Official designation remains separately reviewed.
        for x in range(8):
            world.debug.draw_line(carla.Location(x=x, y=-8, z=.05),
                carla.Location(x=min(x + 2, 7), y=-4, z=.05), thickness=.08,
                color=carla.Color(255, 255, 0), life_time=35, persistent_lines=False)
        for y in (-8, -4):
            world.debug.draw_line(carla.Location(x=0, y=y, z=.05),
                carla.Location(x=7, y=y, z=.05), thickness=.12,
                color=carla.Color(255, 255, 0), life_time=35, persistent_lines=False)
        world.debug.draw_line(carla.Location(x=ROUTE['x_min_m'], y=-8, z=.05),
            carla.Location(x=ROUTE['x_max_m'], y=-8, z=.05), thickness=.08,
            color=carla.Color(255, 255, 255), life_time=35, persistent_lines=False)
        bp = world.get_blueprint_library().find('vehicle.tesla.model3')
        bp.set_attribute('role_name', 'c200542_subject')
        target_y = -2.0 if cfg['case_suffix'] == 'controlled_1' else -6.0
        vehicle = world.try_spawn_actor(bp, carla.Transform(
            carla.Location(x=-20, y=target_y, z=1.3), carla.Rotation(yaw=0)))
        if vehicle is None:
            raise RuntimeError('Original vehicle spawn failed')
        owned.append(vehicle)
        capture = PipelineCapture(client, vehicle, output, cfg['case_id'],
                                  visibility=False,
                                  required_observations=cfg.get('required_atoms', []))
        for name in CAMERAS:
            spec = next(c for c in cfg['cameras'] if c['name'] == name)
            x, y, z, pitch = MOUNTS[name]
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']),
                               ('image_size_y', spec['height']), ('fov', spec['fov_deg']),
                               ('sensor_tick', .05)):
                camera_bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(camera_bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=pitch)))
            owned.append(sensor)
            received = queue.Queue()
            sensor.listen(received.put)
            queues[name] = received
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                '-s', f"{spec['width']}x{spec['height']}", '-r', '20', '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with (output / 'native-vehicle.jsonl').open('x') as motion, \
                (output / 'trace.jsonl').open('x') as trace, \
                FrameMap(output / 'video_frames.jsonl') as frame_map:
            initial_time = None
            for index in range(FRAMES):
                vehicle.set_target_velocity(carla.Vector3D(x=4 if index < 118 else 0, y=0, z=0))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Original snapshot/frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                capture.capture(native_frame, time_s)
                camera_frames = {}
                for name in CAMERAS:
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                transform = vehicle.get_transform()
                velocity = vehicle.get_velocity()
                body = vehicle.bounding_box.get_world_vertices(transform)
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                motion.write(json.dumps({'native_frame': native_frame, 'video_frame': index,
                    'time_s': time_s, 'source_kind': 'original_native', 'actor_id': vehicle.id,
                    'blueprint_id': vehicle.type_id,
                    'center_xy_m': [transform.location.x, transform.location.y],
                    'body_xy_m': [[v.x, v.y, v.z] for v in body], 'speed_mps': speed}) + '\n')
                trace.write(json.dumps({'frame': native_frame, 'time_s': time_s,
                    'position': {'x': transform.location.x, 'y': transform.location.y,
                                 'z': transform.location.z},
                    'position_m': [transform.location.x, transform.location.y, transform.location.z],
                    'heading_deg': transform.rotation.yaw, 'speed_mps': speed}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original FFV1 encoding failed: ' + name + error.decode()[-300:])
        (output / 'aisle-context.json').write_text(json.dumps({'source_kind': 'original_native',
            'cell_id': 'C200542', 'access_aisle': AISLE, 'adjacent_accessible_bay': BAY,
            'accessible_route_diagnostic_extent': ROUTE,
            'premises_public_access_reviewed': False,
            'access_aisle_designation_reviewed': False,
            'marking_source': 'Native diagnostic hatch only; official designation unconfirmed',
            'parked_classification_reviewed': False}, indent=2) + '\n')
        complete = True
        return {'frames': FRAMES, 'camera_names': list(CAMERAS),
                'official_access_aisle_unverified': True, 'physical_acceptance_claimed': False}
    except BaseException as error:
        (output / 'native-run-status.json').write_text(json.dumps({'errors': [str(error)],
            'frames_complete': complete, 'physical_acceptance_claimed': False}, indent=2) + '\n')
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
        restoration = restore(client, saved) if changed else {'restored': True, 'world_unchanged': True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                context={'case_id': cfg['case_id'], 'candidate_id': cfg.get('candidate_id', 'primary'),
                         'premises_designation_and_parking_review': 'pending'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        if not args.output_dir:
            parser.error('--output-dir required')
        print(json.dumps(execute(args.output_dir, args.host, args.port)))
