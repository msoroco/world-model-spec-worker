"""Steady-indication Native capture proposal. CPU --check never contacts CARLA."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from engineering import candidate
from geometry import CROSSWALK_ID, check as geometry_check
from steady import signal_state

HERE = Path(__file__).resolve().parent
RATE_HZ = 20
FRAMES = 240
DEVICE_ID = 'C10316-authored-pedestrian-head-east'


def camera_specs(plan):
    e = plan['engineering']
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080,
         'xyz': [-8, 0, 7], 'yaw': 0, 'pitch': -45},
        {'name': 'approach', 'width': 1280, 'height': 720,
         'xyz': [-6, -4, 3], 'yaw': 35, 'pitch': -20},
        {'name': 'crosswalk_side', 'width': 1280, 'height': 720,
         'xyz': [0, 5, 3], 'yaw': -90, 'pitch': -25},
        {'name': 'display_close', 'width': e['display_camera_width'],
         'height': e['display_camera_height'],
         'xyz': [-3.7-e['display_camera_distance_m'], -2, 2.4],
         'yaw': 0, 'pitch': 0},
    ]


def check(config):
    geometry = geometry_check(HERE / 'road.xodr')
    plan = candidate(config['case_suffix'], config['candidate_id'])
    if config['case_id'] != plan['case_id'] or config['selected_case_id'] != plan['case_id']:
        raise ValueError('Steady-indication case identity differs')
    if (config['cell_id'], config['law_id'], config['actor']) != ('C10316', 'NRS-484B-283-1d4', 'pedestrian'):
        raise ValueError('Frozen assignment identity differs')
    if (config['duration_s'], config['rate_hz']) != (12, RATE_HZ):
        raise ValueError('Full steady capture window differs')
    if [(x['name'], x['width'], x['height']) for x in camera_specs(plan)] != [
        (x['name'], x['width'], x['height']) for x in config['cameras']
    ]:
        raise ValueError('Declared camera contract differs from executable profile')
    states = [signal_state(i, plan['engineering']['steady_start_s']) for i in range(FRAMES)]
    if states[0][0] != 'walk' or states[-1][0] != 'dont_walk_steady':
        raise ValueError('Walk and steady phases absent')
    entry_index = 18
    expected = 'walk' if config['case_suffix'] == 'witness_1' else 'dont_walk_steady'
    if states[entry_index][0] != expected:
        raise ValueError('Requested steady entry phase differs')
    return {'candidate': config['candidate_id'], 'geometry': geometry,
            'frames': FRAMES, 'cameras': [x['name'] for x in camera_specs(plan)],
            'native_imported': False, 'physical_display_verified': False,
            'accepted_recording_claimed': False}


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def footprint(actor):
    points = sorted({(round(v.x, 5), round(v.y, 5))
                     for v in actor.bounding_box.get_world_vertices(actor.get_transform())})
    if len(points) != 4:
        raise RuntimeError('Native walker lacks a four-vertex ground footprint')
    return [list(point) for point in points]


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('Use the newly materialized exact package directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    state = snapshot(client)
    if state['settings'].synchronous_mode or any(
        actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.')) for actor in prior.get_actors()
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
        native_map_hash = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        library = world.get_blueprint_library()
        walkers = sorted(library.filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        if not walkers:
            raise RuntimeError('No Native pedestrian blueprint available')
        walker = world.try_spawn_actor(walkers[0], carla.Transform(
            carla.Location(x=e['spawn_start_x_m'], y=-.65, z=.5), carla.Rotation(yaw=0)))
        if walker is None:
            raise RuntimeError('Native pedestrian spawn failed')
        owned.append(walker)
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
                                                speed=e['walker_speed_mps']))
        for _ in range(round(e['pre_roll_s']*RATE_HZ)):
            world.tick()
        if abs(walker.get_transform().location.x - e['capture_start_x_m']) > .35:
            raise RuntimeError('Observed Native capture start differs from plan')
        capture = PipelineCapture(client, walker, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'steady-samples.jsonl').open('x') as samples, \
             (output / 'video_frames.jsonl').open('x') as frame_map:
            for index in range(FRAMES):
                # Native debug text is a construction probe, not an accepted physical
                # pedestrian signal. Saved pixel and governance audits must reject it
                # if it is absent or does not qualify as the governing indication.
                source_index = (index if e['clock_mode'] == 'frame_index_20hz' else
                    round((world.get_snapshot().timestamp.elapsed_seconds-start)*RATE_HZ))
                if abs(source_index-index) > 1:
                    raise RuntimeError('Observed Native display clock diverges from captured frame')
                proposed, illuminated = signal_state(source_index, e['steady_start_s'])
                if illuminated:
                    world.debug.draw_string(carla.Location(x=-3.7, y=-2, z=2.4),
                        'WALK' if proposed == 'walk' else "DON'T WALK",
                        draw_shadow=True, color=carla.Color(255, 0, 0), life_time=.06)
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = walker.get_transform()
                direction = pose.get_forward_vector()
                speed = walker.get_velocity()
                observed = {'native_frame': frame, 'time_s': time_s,
                            'crosswalk_id': CROSSWALK_ID, 'device_id': DEVICE_ID,
                            'indication': proposed,
                            'display_illuminated': illuminated,
                            'pedestrian_xy_m': [pose.location.x, pose.location.y],
                            'pedestrian_footprint_xy_m': footprint(walker),
                            'observed_walker_speed_mps': math.hypot(speed.x, speed.y),
                            'source_scope': 'Native pose plus requested debug display program; original pixel audit pending'}
                capture.capture(frame, time_s, extra={'steady_proposal': observed})
                pixels = {}
                for spec in camera_specs(plan):
                    image = image_queues[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = image_queues[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Camera and Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:, :, :3][:, :, ::-1]
                    data = rgb.tobytes()
                    pixels[spec['name']] = hashlib.sha256(data).hexdigest()
                    encoders[spec['name']].stdin.write(data)
                observed['original_display_frame_sha256'] = pixels['display_close']
                samples.write(json.dumps(observed, allow_nan=False) + '\n')
                frame_map.write(json.dumps({'video_frame': index, 'native_frame': frame,
                    'carla_frame': frame, 'time_s': time_s, 'source_rgb_sha256': pixels}) + '\n')
                frames += 1
        write_new(output / 'steady-context.json', {
            'source_kind': 'native_observation', 'crosswalk_id': CROSSWALK_ID,
            'device_id': DEVICE_ID, 'device_governs_crosswalk': False,
            'device_faces_pedestrian': False,
            'near_highway_edge_xy_m': [-3.5, -.65], 'crossing_forward_xy': [1, 0],
            'highway_span_m': 7, 'highway_boundary_source': 'authored_map_pending_native_review',
            'authored_map_sha256': hashlib.sha256((HERE / 'road.xodr').read_bytes()).hexdigest(),
            'native_map_sha256': native_map_hash, 'observed_frame_count': frames,
            'display_pixel_audit_sha256': None, 'steady_start_s': e['steady_start_s'],
            'lawful_prior_entry_review': 'unverified',
            'safety_destination_review': 'unverified',
            'as_soon_as_possible_judgment_bound': None,
            'introductory_exceptions': 'unreviewed'})
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try: capture.close(confirmed=error is None)
            except BaseException as exc: error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: ' + name)
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
            'error': error, 'accepted': False,
            'physical_display_verified': False, 'governing_device_verified': False,
            'display_pixels_independently_audited': False})
    if error:
        raise RuntimeError('Native steady attempt failed; inspect native-capture-report.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads((HERE / 'config.json').read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            raise ValueError('Explicit materialized package and owned Native endpoint required')
        execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
