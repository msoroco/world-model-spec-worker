"""One-way direction capability capture using native actuation and shared capture."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from scenario import build_xodr, route, static_check

ROOT = Path(__file__).resolve().parent


def config():
    return json.loads((ROOT / 'config.json').read_text())


def check():
    cfg = config()
    case = cfg['case']
    assert cfg['law_id'] == 'NRS-484B-220-1'
    assert cfg['actor'] == 'motor_vehicle_driver'
    assert cfg['selected_case_id'] == case['case_id']
    assert case['variable_assignments']['test_branch']['value'] in ('designated_direction', 'opposite_direction')
    assert len(cfg['cameras']) == 4
    assert (cfg['cameras'][0]['width'], cfg['cameras'][0]['height']) == (1920, 1080)
    assert all((c['width'], c['height']) == (1280, 720) for c in cfg['cameras'][1:])
    assert set(cfg['required_atoms']) <= {c['name'] for c in case['recording_description']['channels']}
    path = route(case)
    assert len(path) == 231
    assert all(abs(a[0]-b[0]) == 1 and a[1] == b[1] for a, b in zip(path, path[1:]))
    print(json.dumps({'case_id': case['case_id'], 'offline_passed': True,
                      'geometry': static_check(), 'simulator_connected': False}))


def image_for_frame(q, frame):
    image = q.get(timeout=30)
    while image.frame < frame:
        image = q.get(timeout=30)
    if image.frame != frame:
        raise RuntimeError('Camera/source frame mismatch')
    return image


def control(carla, ego, points, target_speed):
    transform = ego.get_transform()
    x, y = transform.location.x, transform.location.y
    index = min(range(len(points)), key=lambda i: (points[i][0]-x)**2+(points[i][1]-y)**2)
    target = points[min(index+7, len(points)-1)]
    heading = math.atan2(target[1]-y, target[0]-x)
    error = (heading-math.radians(transform.rotation.yaw)+math.pi) % (2*math.pi)-math.pi
    speed = ego.get_velocity().length()
    desired = min(target_speed, max(0, .2*(len(points)-1-index)))
    return carla.VehicleControl(throttle=max(0, min(.55, .3*(desired-speed))),
                                brake=max(0, min(.75, .4*(speed-desired))),
                                steer=max(-1, min(1, 1.5*error))), index


def append_frame_map(writer, frame, time_s, source_frames):
    """Write the original sensor/source identity at the same recorded tick."""
    return writer.append(frame, time_s, source_frames=source_frames)


def run(args):
    import carla  # live path only
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    cfg = config()
    case = cfg['case']
    path = route(case)
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'physical_samples.jsonl').exists():
        raise ValueError('Choose a fresh output directory and retain prior attempts')
    if not (output / 'config.json').exists():
        (output / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    client = carla.Client(args.host, args.port)
    client.set_timeout(90)
    if client.get_client_version() != client.get_server_version():
        raise RuntimeError('CARLA client/server version mismatch')
    saved_world = snapshot(client)
    world = None
    actors, cameras, encoders = [], [], []
    channels = {}
    capture = None
    count = 0
    completed = False
    error = None
    try:
        world = client.generate_opendrive_world(build_xodr())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        bp = world.get_blueprint_library().find('vehicle.tesla.model3')
        bp.set_attribute('role_name', 'ego')
        yaw = 0 if path[-1][0] > path[0][0] else 180
        ego = world.spawn_actor(bp, carla.Transform(carla.Location(x=path[0][0], y=path[0][1], z=.5), carla.Rotation(yaw=yaw)))
        actors.append(ego)
        native = {'map': world.get_map().name, 'lane_direction': 'eastbound right-side lanes -1,-2',
                  'synthetic_context': cfg['authored_test_context'],
                  'native_signs': [{'id': x.id, 'name': x.name, 'road_id': x.road_id, 's': x.s}
                                   for x in world.get_map().get_all_landmarks()]}
        (output / 'native-setup.json').write_text(json.dumps(native, indent=2) + '\n')
        for i, spec in enumerate(cfg['cameras']):
            cb = world.get_blueprint_library().find('sensor.camera.rgb')
            cb.set_attribute('image_size_x', str(spec['width']))
            cb.set_attribute('image_size_y', str(spec['height']))
            cb.set_attribute('sensor_tick', '0')
            loc = spec['location']
            sensor = world.spawn_actor(cb, carla.Transform(carla.Location(x=loc[0], y=loc[1], z=loc[2]),
                                                    carla.Rotation(pitch=spec['pitch'])), attach_to=ego)
            actors.append(sensor)
            q = queue.Queue()
            sensor.listen(q.put)
            log = (output / ('view%d.encoder.log' % i)).open('x')
            encoder = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', '%dx%d' % (spec['width'], spec['height']),
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgr0', str(output / ('view%d.mkv' % i))],
                stdin=subprocess.PIPE, stderr=log)
            cameras.append((sensor, q))
            encoders.append((encoder, log))
        for _ in range(5):
            world.tick()
        capture = PipelineCapture(client, ego, output, case['case_id'], required_observations=cfg['required_atoms'])
        evidence_reader = (output / 'capture/evidence.jsonl').open()
        (output / 'channels').mkdir()
        channels = {c['name']: (output / 'channels' / (c['name'] + '.jsonl')).open('x')
                    for c in case['recording_description']['channels']}
        (output / 'context.json').write_text(json.dumps(cfg['authored_test_context'], indent=2) + '\n')
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'physical_samples.jsonl').open('x') as raw, FrameMap(output / 'video_frames.jsonl') as mapping:
            for i in range(cfg['max_ticks']):
                request, index = control(carla, ego, path, 8)
                ego.apply_control(request)
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - start
                row = capture.capture(frame, now)
                event = json.loads(evidence_reader.readline())
                if event['original_frame'] != frame:
                    raise RuntimeError('Original observations not synchronized')
                transform = ego.get_transform()
                vertices = [[v.x, v.y, v.z] for v in ego.bounding_box.get_world_vertices(transform)]
                sample = {'frame': frame, 'time_s': now, 'position_m': row['position_m'],
                          'heading_deg': row['heading_deg'], 'speed_mps': row['speed_mps'],
                          'body_vertices_m': vertices, 'route_index': index, 'control': row['control']}
                raw.write(json.dumps(sample) + '\n')
                for name, stream in channels.items():
                    stream.write(json.dumps({'time_s': now, 'value': {
                        'original_observations': event['original_observations'], 'physical_sample': sample}}) + '\n')
                source_frames = {}
                for (sensor, q), (encoder, _) in zip(cameras, encoders):
                    image = image_for_frame(q, frame)
                    pixels = bytes(image.raw_data)
                    encoder.stdin.write(pixels)
                    source_frames[str(sensor.id)] = {'native_frame': image.frame,
                        'source_bgra_sha256': hashlib.sha256(pixels).hexdigest(),
                        'width': image.width, 'height': image.height}
                append_frame_map(mapping, frame, now, source_frames)
                count += 1
                if index >= len(path)-2 and row['speed_mps'] < 2:
                    completed = True
                    break
    except BaseException as exc:
        error = repr(exc)
    finally:
        cleanup_errors = []
        def finish(name, action):
            try:
                action()
            except BaseException as exc:
                cleanup_errors.append({'action': name, 'error': repr(exc)})
        for name, stream in channels.items():
            finish('channel:' + name, stream.close)
        if 'evidence_reader' in locals():
            finish('evidence_reader', evidence_reader.close)
        if capture:
            finish('capture', lambda: capture.close(confirmed=completed and error is None))
        for index, (encoder, log) in enumerate(encoders):
            finish('encoder_stdin:%d' % index, encoder.stdin.close)
            finish('encoder_wait:%d' % index, lambda encoder=encoder: encoder.wait(timeout=120))
            finish('encoder_log:%d' % index, log.close)
        for actor in reversed(actors):
            finish('actor:%s' % actor.id, actor.destroy)
        if world is not None:
            def restore_world():
                receipt = restore(client, saved_world)
                (output / 'world-restoration.json').write_text(json.dumps(receipt, indent=2) + '\n')
            finish('world_restore', restore_world)
        if cleanup_errors:
            (output / 'cleanup-errors.json').write_text(json.dumps(cleanup_errors, indent=2) + '\n')
            error = (error + '; ' if error else '') + 'cleanup/restoration failed: ' + repr(cleanup_errors)
    (output / 'capability-run.json').write_text(json.dumps({'case_id': case['case_id'],
        'recorded_frames': count, 'route_completed': completed, 'error': error,
        'physical_acceptance': False, 'unverified': ['native sign rendering and governance',
        'full body lane occupancy', 'camera visibility', 'mandatory source coverage', 'final decoded videos']}, indent=2) + '\n')
    if error or not completed:
        raise RuntimeError('Capability run incomplete; inspect retained evidence')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--output-dir')
    p.add_argument('--host')
    p.add_argument('--port', type=int)
    a = p.parse_args()
    if a.check:
        check()
    else:
        if not (a.output_dir and a.host and a.port):
            p.error('Live capture requires output-dir, host and port')
        run(a)
