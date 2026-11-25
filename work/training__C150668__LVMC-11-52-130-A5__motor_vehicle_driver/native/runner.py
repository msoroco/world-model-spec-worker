"""Original Native curb/fixture acquisition draft; fixture identity needs review."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess

from geometry import FIXTURE_BOUNDS, SIDEWALK_BOUNDS, check as geometry_check, open_drive
from stop_route import FRAMES, RATE_HZ, STOP_X_M, command

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check(config):
    geometry = geometry_check()
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C150668', 'LVMC-11-52-130-A5', 'motor_vehicle_driver'):
        raise ValueError('exact assignment identity changed')
    selected = {'probe_1': ('outside', 'none'),
                'probe_2': ('side_band', 'none'),
                'probe_3': ('front', 'none'),
                'probe_4': ('side_band', 'traffic_conflict'),
                'probe_5': ('side_band', 'police_direction'),
                'probe_6': ('side_band', 'device_direction'),
                'probe_7': ('at_five_feet', 'none')}
    suffix = config['case_id'].rsplit('__', 1)[-1]
    if (config['stop_case'], config.get('exception_mode', 'none')) != selected.get(suffix):
        raise ValueError('unknown exact stop case')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != FRAMES / RATE_HZ:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four original source cameras required')
    return {'geometry': geometry, 'frames': FRAMES, 'camera_names': CAMERAS,
            'native_imported': False, 'fixture_identity_observed': False,
            'physical_acceptance_claimed': False}


def survey(carla, mapping):
    points = []
    for x in (-60, -20, 0, 5, 10, 40):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1.4),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1 or abs(wp.transform.location.x - x) > 1:
            raise RuntimeError('Native one-way fixture lane survey failed')
        points.append({'x_m': x, 'road_id': wp.road_id, 'lane_id': wp.lane_id,
                       'native_xyz_m': [wp.transform.location.x, wp.transform.location.y,
                                        wp.transform.location.z]})
    sidewalk = mapping.get_waypoint(carla.Location(x=1, y=1.5, z=1.4),
                                    project_to_road=True, lane_type=carla.LaneType.Sidewalk)
    if sidewalk is None or sidewalk.road_id != 1 or sidewalk.lane_id != 1:
        raise RuntimeError('Native sidewalk lane survey failed')
    return points


def footprint(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    if not points:
        raise RuntimeError('Native vehicle body vertices missing')
    return {'min_x': min(p.x for p in points), 'max_x': max(p.x for p in points),
            'min_y': min(p.y for p in points), 'max_y': max(p.y for p in points)}


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'vehicle-poses.jsonl').exists():
        raise ValueError('new materialized attempt required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('exclusive idle Native world required')
    owned, encoders, camera_queues = [], {}, {}
    changed = False
    failure, errors, encoder_codes = None, [], {}
    restoration = {'restored': False}
    completed = 0
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
        readback = survey(carla, world.get_map())
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        library = world.get_blueprint_library()
        bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        bp.set_attribute('role_name', 'c150668_subject')
        vehicle = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=-60, y=-1.75, z=2), carla.Rotation(yaw=0)))
        owned.append(vehicle)
        fixture_id = config.get('fixture_blueprint_id') or os.environ.get('C150668_FIXTURE_BLUEPRINT_ID')
        if fixture_id:
            fixture_bp = library.find(fixture_id)
        else:
            fixture_bps = sorted(library.filter('static.prop.box*'), key=lambda b: b.id)
            if not fixture_bps:
                raise RuntimeError('Native sidewalk fixture proxy blueprint unavailable')
            fixture_bp = fixture_bps[0]
        fixture = world.spawn_actor(fixture_bp, carla.Transform(
            carla.Location(x=1, y=1, z=1.3), carla.Rotation(yaw=0)))
        owned.append(fixture)
        mode = config.get('exception_mode', 'none')
        exception_actor = None
        if mode == 'traffic_conflict':
            other_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
            other_bp.set_attribute('role_name', 'c150668_traffic_conflict_actor')
            exception_actor = world.spawn_actor(other_bp, carla.Transform(
                carla.Location(x=11, y=-1.75, z=2), carla.Rotation(yaw=0)))
            exception_actor.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
        elif mode == 'police_direction':
            officer_id = os.environ.get('C150668_OFFICER_BLUEPRINT_ID')
            if not officer_id:
                raise RuntimeError('Original officer blueprint source required')
            exception_actor = world.spawn_actor(library.find(officer_id), carla.Transform(
                carla.Location(x=4, y=1.5, z=1.1), carla.Rotation(yaw=180)))
        elif mode == 'device_direction':
            device_id = os.environ.get('C150668_DEVICE_BLUEPRINT_ID')
            if not device_id:
                raise RuntimeError('Original traffic-control-device blueprint source required')
            exception_actor = world.spawn_actor(library.find(device_id), carla.Transform(
                carla.Location(x=4, y=1.5, z=1.1), carla.Rotation(yaw=180)))
        if exception_actor is not None:
            owned.append(exception_actor)
        (output / 'fixture-inventory.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C150668',
            'native_lane_survey': readback, 'fixture_bounds_m': footprint(fixture),
            'sidewalk_bounds_m': SIDEWALK_BOUNDS,
            'fixture_proxy_blueprint_id': fixture.type_id if fixture.type_id.startswith('static.prop.box') else None,
            'fixture_blueprint_id': fixture.type_id,
            'fixture_identity_verified': False, 'police_direction_source': None,
            'traffic_control_device_source': None, 'traffic_conflict_source': None,
            'exception_mode': mode,
            'exception_actor_id': exception_actor.id if exception_actor is not None else None,
            'exception_actor_blueprint_id': exception_actor.type_id if exception_actor is not None else None}, indent=2) + '\n')
        mounts = {'overview': (5, -20, 22, -35), 'approach': (-20, -8, 9, -15),
                  'reference_corner': (1, 8, 9, -20), 'driver_reference': (-30, 7, 10, -20)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            cbp = library.find('sensor.camera.rgb')
            cbp.set_attribute('image_size_x', str(spec['width']))
            cbp.set_attribute('image_size_y', str(spec['height']))
            cbp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            camera = world.spawn_actor(cbp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with PipelineCapture(client, vehicle, output, config['case_id'],
                required_observations=config.get('required_atoms', [])) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'vehicle-poses.jsonl').open('x') as poses, \
                (output / 'trace.jsonl').open('x') as trace:
            initial_time = None
            for index in range(FRAMES):
                vt, vv = vehicle.get_transform(), vehicle.get_velocity()
                speed = math.hypot(vv.x, vv.y)
                request = command(config['stop_case'], index, vt.location.x, speed,
                                  config.get('brake_margin_m', 1.5))
                vehicle.apply_control(carla.VehicleControl(
                    throttle=request['throttle'], brake=request['brake'], steer=request['steer']))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                camera_frames = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                capture.capture(native_frame, time_s, extra={'video_frame': index})
                vt, vv = vehicle.get_transform(), vehicle.get_velocity()
                trace.write(json.dumps({'frame': native_frame, 'time_s': time_s,
                    'position': {'x': vt.location.x, 'y': vt.location.y,
                                 'z': vt.location.z},
                    'heading_deg': vt.rotation.yaw,
                    'speed_mps': math.hypot(vv.x, vv.y),
                    'stop_case_request': config['stop_case']}) + '\n')
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'vehicle_id': vehicle.id, 'fixture_actor_id': fixture.id,
                    'vehicle_xyz_m': [vt.location.x, vt.location.y, vt.location.z],
                    'observed_vehicle_speed_mps': math.hypot(vv.x, vv.y),
                    'vehicle_footprint_m': footprint(vehicle),
                    'requested_control': request, 'camera_native_frames': camera_frames,
                    'fixture_identity_verified': False}) + '\n')
                completed += 1
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            if encoder_codes[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        review_dir = os.environ.get('C150668_FIXTURE_REVIEW_DIR')
        if review_dir:
            review_dir = Path(review_dir).resolve()
            if not review_dir.is_dir():
                raise ValueError('Reviewed fixture source directory missing')
            destination = output / 'fixture-review'
            destination.mkdir(exist_ok=False)
            from source_review import ROLES, reviewed_context
            for role in ROLES:
                for suffix in ('.json', '.source.txt'):
                    source = review_dir / (role + suffix)
                    if not source.is_file():
                        raise ValueError('Reviewed fixture role missing: ' + role + suffix)
                    shutil.copy2(source, destination / source.name)
            reviewed_context(output)
    except BaseException as error:
        failure = error
        errors.append(f'{type(error).__name__}: {error}')
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
            try:
                restoration = restore(client, saved)
            except Exception as error:
                errors.append(f'world restore: {error}')
        if output.exists():
            (output / 'native-run-status.json').write_text(json.dumps({
                'case_id': config['case_id'], 'frames': completed,
                'errors': errors, 'restoration': restoration,
                'encoder_exit_codes': encoder_codes,
                'capture_finished': completed == FRAMES and failure is None,
                'acceptance_claimed': False}, indent=2) + '\n')
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError('; '.join(errors))
    seal_capture(output, frames=completed, restoration=restoration, errors=errors,
                 encoder_exit_codes=encoder_codes,
                 context={'case_id': config['case_id'],
                          'source': 'original Native CARLA capture',
                          'fixture_identity_verified': False})
    return {'frames': completed, 'fixture_source_review_required': True,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required')
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
