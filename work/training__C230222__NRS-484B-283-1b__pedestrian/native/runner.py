"""Curb-entry Native construction. --check is CPU only; execute requires an owned CARLA world."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import traceback

from engineering import candidate
from geometry import check as geometry_check

HERE = Path(__file__).resolve().parent
RATE_HZ = 20
FRAMES = 240


def camera_specs(plan):
    e = plan['engineering']
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080,
         'xyz': [-9, 1, 8], 'yaw': 0, 'pitch': -45},
        {'name': 'vehicle_approach', 'width': 1280, 'height': 720,
         'xyz': [-6, -8, 3], 'yaw': 45, 'pitch': -20},
        {'name': 'curb_side', 'width': 1280, 'height': 720,
         'xyz': [2, 5, 3], 'yaw': -125, 'pitch': -25},
        {'name': 'curb_close', 'width': e['camera_width'], 'height': e['camera_height'],
         'xyz': [-3.5-e['camera_distance_m'], -2, 2.5], 'yaw': 0, 'pitch': -8},
    ]


def check(config):
    geometry = geometry_check()
    plan = candidate(config['case_suffix'], config['candidate_id'])
    if config['case_id'] != plan['case_id'] or config.get('selected_case_id') != plan['case_id']:
        raise ValueError('Curb case identity differs')
    if (config['cell_id'], config['law_id'], config['actor']) != ('C230222', 'NRS-484B-283-1b', 'pedestrian'):
        raise ValueError('Frozen curb identity differs')
    if (config['duration_s'], config['rate_hz']) != (12, RATE_HZ):
        raise ValueError('Full curb capture window differs')
    if [(x['name'], x['width'], x['height']) for x in config['cameras']] != [
        (x['name'], x['width'], x['height']) for x in camera_specs(plan)]:
        raise ValueError('Curb camera contract differs')
    if plan['engineering']['pedestrian_departure_s'] not in (.5, 3.5):
        raise ValueError('Controlled curb departure differs')
    return {'candidate': config['candidate_id'], 'geometry': geometry, 'frames': FRAMES,
            'cameras': [x['name'] for x in camera_specs(plan)], 'native_imported': False,
            'actual_driver_yield_measured': False, 'impossibility_to_yield_proven': False,
            'accepted_recording_claimed': False}


def footprint(actor):
    points = sorted({(round(v.x, 5), round(v.y, 5))
                     for v in actor.bounding_box.get_world_vertices(actor.get_transform())})
    if len(points) != 4:
        raise RuntimeError('Native pedestrian lacks four ground footprint vertices')
    return [list(p) for p in points]


def write_new(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use a newly materialized exact package directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    state = snapshot(client)
    if state['settings'].synchronous_mode or any(
        a.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for a in prior.get_actors()
    ):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    plan = candidate(config['case_suffix'], config['candidate_id'])
    e = plan['engineering']
    owned, encoders, logs, image_queues = [], {}, {}, {}
    capture = None
    changed = False
    error = None
    restored = None
    frames = 0
    try:
        world = client.generate_opendrive_world((HERE / 'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=True))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/RATE_HZ
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        native_map_sha = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        library = world.get_blueprint_library()
        walkers = sorted(library.filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        vehicles = sorted(library.filter('vehicle.*'), key=lambda bp: bp.id)
        if not walkers or not vehicles:
            raise RuntimeError('Native pedestrian or vehicle blueprint unavailable')
        walker = world.try_spawn_actor(walkers[0], carla.Transform(
            carla.Location(x=e['pedestrian_spawn_x_m'], y=0, z=.5), carla.Rotation(yaw=0)))
        vehicle = world.try_spawn_actor(vehicles[0], carla.Transform(
            carla.Location(x=-1.75, y=e['vehicle_start_y_m'], z=.5), carla.Rotation(yaw=90)))
        if walker is None or vehicle is None:
            raise RuntimeError('Native curb actor spawn failed')
        owned.extend((walker, vehicle))
        for spec in camera_specs(plan):
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            x, y, z = spec['xyz']
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                carla.Rotation(yaw=spec['yaw'], pitch=spec['pitch'])))
            owned.append(sensor)
            image_queues[spec['name']] = queue.Queue()
            sensor.listen(image_queues[spec['name']].put)
            logs[spec['name']] = (output / (spec['name'] + '.encoder.log')).open('x')
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ),
                '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output / (spec['name'] + '.mkv'))], stdin=subprocess.PIPE,
                stderr=logs[spec['name']])
        walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=1),
                                                speed=e['pedestrian_target_speed_mps'] if e['pedestrian_pre_roll_s'] else 0))
        for _ in range(round(e['pedestrian_pre_roll_s']*RATE_HZ)):
            world.tick()
        walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=1), speed=0))
        vehicle.set_target_velocity(carla.Vector3D(y=e['vehicle_target_speed_mps']))
        if abs(walker.get_transform().location.x + 4.5) > .35:
            raise RuntimeError('Observed Native curb capture start differs from plan')
        capture = PipelineCapture(client, walker, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'curb-samples.jsonl').open('x') as samples, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(FRAMES):
                requested_speed = e['pedestrian_target_speed_mps'] if index/RATE_HZ >= e['pedestrian_departure_s'] else 0
                if e['pedestrian_control'] == 'bounded_acceleration_to_target_velocity':
                    requested_speed = min(requested_speed, max(0, index/RATE_HZ-e['pedestrian_departure_s'])*4)
                walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=1), speed=requested_speed))
                vehicle.set_target_velocity(carla.Vector3D(y=e['vehicle_target_speed_mps']))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds-start
                ped_pose, veh_pose = walker.get_transform(), vehicle.get_transform()
                ped_velocity, veh_velocity = walker.get_velocity(), vehicle.get_velocity()
                observed = {'native_frame': frame, 'time_s': time_s,
                    'pedestrian_id': walker.id, 'vehicle_id': vehicle.id,
                    'pedestrian_xy_m': [ped_pose.location.x, ped_pose.location.y],
                    'pedestrian_footprint_xy_m': footprint(walker),
                    'pedestrian_speed_mps': math.hypot(ped_velocity.x, ped_velocity.y),
                    'vehicle_xy_m': [veh_pose.location.x, veh_pose.location.y],
                    'vehicle_speed_mps': math.hypot(veh_velocity.x, veh_velocity.y)}
                capture.capture(frame, time_s, extra={'curb_proposal': observed})
                pixels = {}
                for spec in camera_specs(plan):
                    image = image_queues[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = image_queues[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Curb camera and Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    data = rgb.tobytes()
                    pixels[spec['name']] = hashlib.sha256(data).hexdigest()
                    encoders[spec['name']].stdin.write(data)
                observed['original_frame_sha256'] = pixels['curb_close']
                samples.write(json.dumps(observed, allow_nan=False) + '\n')
                frame_map.write(json.dumps({'video_frame': index, 'native_frame': frame,
                    'carla_frame': frame, 'time_s': time_s, 'source_rgb_sha256': pixels}) + '\n')
                frames += 1
        write_new(output / 'curb-context.json', {
            'source_kind': 'native_observation',
            'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'},
            'authored_road_sha256': hashlib.sha256((HERE / 'road.xodr').read_bytes()).hexdigest(),
            'native_road_sha256': native_map_sha,
            'vehicle_source_audit_sha256': hashlib.sha256((output / 'video_frames.jsonl').read_bytes()).hexdigest(),
            'road_width_m': 7, 'vehicle_conflict_y_m': 0, 'curb_edge_xy_m': [-3.5, 0],
            'pedestrian_crossing_forward_xy': [1, 0], 'pedestrian_id': walker.id,
            'vehicle_id': vehicle.id, 'vehicle_lane_center_x_m': -1.75,
            'vehicle_body_half_width_m': 1.0,
            'assumed_driver_reaction_s': [.8, 1.2],
            'assumed_deceleration_mps2': [3.0, 5.0],
            'driver_capability_measured': False, 'introductory_exceptions_reviewed': False})
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try: capture.close(confirmed=False)
            except BaseException as exc: error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless curb encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        if changed:
            try: restored = restore(client, state)
            except BaseException as exc: error = error or {'world_restore_error': str(exc)}
        write_new(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'frames': frames, 'expected_frames': FRAMES, 'restoration': restored,
            'error': error, 'accepted': False, 'driver_capability_measured': False,
            'impossibility_to_yield_proven': False})
    if error:
        raise RuntimeError('Native curb attempt failed; inspect native-capture-report.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--config', type=Path, default=HERE / 'config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            raise ValueError('Explicit materialized package and owned Native endpoint required')
        execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
