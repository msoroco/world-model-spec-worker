"""Prospective original Native marked-lane/shoulder episode; no legal verdict."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess

from native.controlled_access_road import inspect, open_drive, planned_xy


ASSIGNMENT = 'training__C179776__NRS-484B-587-2a__motor_vehicle_driver'
CASES = {'probe_a': 'marked_lane', 'probe_b': 'paved_shoulder'}
CAMERAS = (
    ('overview', 1920, 1080, -8, 0, 13, -35),
    ('approach', 1280, 720, -12, -5, 6, -12),
    ('reference_corner', 1280, 720, -4, 4, 7, -25),
    ('driver_reference', 1280, 720, -1, 0, 3, -5),
)


def check(case_id):
    if not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('Frozen assignment identity differs')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if suffix not in CASES:
        raise ValueError('Unknown selected case')
    if len(CAMERAS) != 4 or len({name for name, *_ in CAMERAS}) != 4:
        raise ValueError('Four camera profile missing')
    return inspect(CASES[suffix])


def survey(world, carla):
    samples = []
    for lane_id, lane_type, y in ((1, carla.LaneType.Driving, 2),
                                  (2, carla.LaneType.Shoulder, 5),
                                  (-1, carla.LaneType.Driving, -2)):
        for x in (15, 75, 130):
            waypoint = world.get_map().get_waypoint(
                carla.Location(x=x, y=y, z=0.5), project_to_road=True,
                lane_type=lane_type)
            if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != lane_id:
                raise RuntimeError('Original Native lane or shoulder readback differs')
            if abs(waypoint.transform.location.y - y) > .35:
                raise RuntimeError('Original Native lateral geometry differs')
            samples.append({'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                            'lane_type': str(waypoint.lane_type), 'x_m': x,
                            'center_y_m': waypoint.transform.location.y,
                            'width_m': waypoint.lane_width})
    return samples


def _speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def _control(actor, target, carla, controller=None):
    controller = controller or {}
    pose = actor.get_transform()
    wanted_yaw = math.atan2(target[1] - pose.location.y, target[0] - pose.location.x)
    error = math.atan2(math.sin(wanted_yaw - math.radians(pose.rotation.yaw)),
                       math.cos(wanted_yaw - math.radians(pose.rotation.yaw)))
    delta = 4.0 - _speed(actor)
    return carla.VehicleControl(throttle=max(0, min(.45, delta * controller.get('throttle_gain', .22))),
                                brake=max(0, min(1, -delta * .38)),
                                steer=max(-.65, min(.65, error * controller.get('steer_gain', 1.2))))


def execute(case_id, output_dir, authority_packet, host='127.0.0.1', port=2000,
            controller=None):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(case_id)
    source = Path(authority_packet).resolve()
    if not source.is_file():
        raise ValueError('Independent controlled-access authority packet missing')
    packet = json.loads(source.read_text())
    if not all(packet.get(key) for key in ('public_authority_source',
                                           'highway_boundary_source',
                                           'access_restriction_source',
                                           'vehicle_class_source',
                                           'emergency_event_source',
                                           'sign_source')):
        raise ValueError('Independent controlled-access designation source incomplete')
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Original Native attempt path already occupied')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    if saved['settings'].synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in client.get_world().get_actors()):
        raise RuntimeError('Requires exclusive idle asynchronous Native world')
    owned, encoders, cameras, errors, encoder_codes = [], {}, {}, [], {}
    changed, completed, failure, restoration = False, 0, None, {'restored': False}
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        readback = survey(world, carla)
        output.mkdir(parents=True)
        shutil.copy2(source, output / 'designation-source.json')
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'native-road-readback.json').write_text(json.dumps({
            'source_kind': 'original_native_map_readback', 'lanes': readback,
            'designation_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'entrance_exit_lane_survey_complete': False,
            'physical_marking_pixel_review_complete': False}, indent=2) + '\n')
        blueprints = sorted(world.get_blueprint_library().filter('vehicle.*'),
                            key=lambda item: item.id)
        if not blueprints:
            raise RuntimeError('Vehicle blueprint missing')
        blueprint = blueprints[0]
        blueprint.set_attribute('role_name', 'c179776_ego')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=132, y=2.5, z=.6), carla.Rotation(yaw=180)))
        owned.append(ego)
        for name, width, height, x, y, z, pitch in CAMERAS:
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('fov', '85')
            blueprint.set_attribute('sensor_tick', '.05')
            camera = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)),
                attach_to=ego)
            owned.append(camera)
            frames = queue.Queue()
            camera.listen(frames.put)
            cameras[name] = frames
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', '20', '-i', '-', '-frames:v', '600', '-c:v', 'ffv1', '-level',
                '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with PipelineCapture(client, ego, output, case_id,
                             required_observations=['kin.position', 'kin.speed']) as capture, (
                             FrameMap(output / 'video_frames.jsonl')) as frame_map, (
                             output / 'native-raw-actors.jsonl').open('x') as raw, (
                             output / 'control-intent.jsonl').open('x') as controls, (
                             output / 'trace.jsonl').open('x') as trace:
            first_elapsed = None
            target_name = CASES[case_id.removeprefix(ASSIGNMENT + '__')]
            for index in range(600):
                target = planned_xy(target_name, index / 20)
                command = _control(ego, target, carla, controller)
                ego.apply_control(command)
                native = world.tick()
                snap = world.get_snapshot()
                if native != snap.frame:
                    raise RuntimeError('Original Native frame identity differs')
                if first_elapsed is None:
                    first_elapsed = snap.timestamp.elapsed_seconds
                elapsed = snap.timestamp.elapsed_seconds - first_elapsed
                pose = ego.get_transform()
                extent = ego.bounding_box.extent
                observed = {'role': 'ego', 'actor_id': ego.id,
                            'blueprint_id': ego.type_id, 'x_m': pose.location.x,
                            'y_m': pose.location.y, 'yaw_deg': pose.rotation.yaw,
                            'bbox_half_length_m': extent.x,
                            'bbox_half_width_m': extent.y,
                            'speed_mps': _speed(ego)}
                mapped = {}
                for name, frames in cameras.items():
                    image = frames.get(timeout=30)
                    while image.frame < native:
                        image = frames.get(timeout=30)
                    if image.frame != native:
                        raise RuntimeError('Original camera frame join differs: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native, elapsed, camera_native_frames=mapped)
                capture.capture(native, elapsed, extra={'video_frame': index})
                raw.write(json.dumps({'video_frame': index, 'native_frame': native,
                                      'time_s': elapsed, 'case_id': case_id,
                                      'actors': [observed]}) + '\n')
                controls.write(json.dumps({'video_frame': index, 'native_frame': native,
                                           'time_s': elapsed, 'target_xy_m': target,
                                           'target_speed_mps': 4.0,
                                           'throttle': command.throttle,
                                           'brake': command.brake,
                                           'steer': command.steer}) + '\n')
                trace.write(json.dumps({'frame': native, 'time_s': elapsed,
                                        'position': {'x': observed['x_m'],
                                                     'y': observed['y_m'], 'z': 0},
                                        'heading_deg': observed['yaw_deg'],
                                        'speed_mps': observed['speed_mps']}) + '\n')
                completed += 1
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            if encoder_codes[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Camera encoding failed: ' + name + ': ' + stderr.decode()[-400:])
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
            except Exception as error:
                errors.append('actor destroy: ' + str(error))
        if changed:
            try:
                restoration = restore(client, saved)
            except Exception as error:
                errors.append('world restore: ' + str(error))
        if output.exists():
            (output / 'native-run-status.json').write_text(json.dumps({
                'case_id': case_id, 'frames': completed, 'errors': errors,
                'restoration': restoration, 'encoder_exit_codes': encoder_codes,
                'capture_finished': completed == 600 and failure is None,
                'acceptance_claimed': False}, indent=2) + '\n')
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError('; '.join(errors))
    seal_capture(output, frames=completed, restoration=restoration,
                 errors=errors, encoder_exit_codes=encoder_codes,
                 context={'case_id': case_id, 'source': 'original Native CARLA capture',
                          'legal_verdict': None})
    return {'native_frames': completed, 'camera_names': list(cameras),
            'physical_completion_claimed': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--authority-packet')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text()) if Path('config.json').is_file() else {}
    case_id = args.case or config.get('case_id')
    if not case_id:
        raise SystemExit('--case or config.json case_id required')
    if args.check:
        print(json.dumps(check(case_id), sort_keys=True))
    else:
        if not args.output_dir or not args.authority_packet:
            raise SystemExit('--output-dir and --authority-packet required')
        print(json.dumps(execute(case_id, args.output_dir,
                                 args.authority_packet, args.host, args.port,
                                 config.get('controller')), sort_keys=True))
