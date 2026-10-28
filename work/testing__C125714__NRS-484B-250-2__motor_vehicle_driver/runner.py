"""Recorded same-time crossing arrival sweep; no judgment verdict."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from scenario import build_xodr, inside_crossing, route, static_check

ROOT = Path(__file__).resolve().parent


def config():
    return json.loads((ROOT / 'config.json').read_text())


def check():
    cfg = config()
    case = cfg['case']
    assert case['case_id'] == cfg['selected_case_id']
    assert cfg['law_id'] == 'NRS-484B-250-2'
    assert case['target_type'] == 'judgment_sweep'
    assert case['variable_assignments']['commanded_release_delay_s']['value'] in (1, 2, 3, 4, 5)
    assert cfg['actor'] == 'motor_vehicle_driver'
    assert len(cfg['cameras']) == 4
    assert (cfg['cameras'][0]['width'], cfg['cameras'][0]['height']) == (1920, 1080)
    assert all((c['width'], c['height']) == (1280, 720) for c in cfg['cameras'][1:])
    required = set(cfg['required_atoms'])
    assert required <= {c['name'] for c in case['recording_description']['channels']}
    for role in ('ego', 'other'):
        points = route(role)
        assert len(points) > 70
        assert all(math.dist(a, b) <= 1.01 for a, b in zip(points, points[1:]))
    print(json.dumps({'case_id': case['case_id'], 'offline_passed': True, 'map': static_check(),
                      'simulator_connected': False}))


def control(carla, actor, points, speed_target):
    t = actor.get_transform()
    x, y = t.location.x, t.location.y
    index = min(range(len(points)), key=lambda i: (points[i][0]-x)**2+(points[i][1]-y)**2)
    target = points[min(index+6, len(points)-1)]
    bearing = math.atan2(target[1]-y, target[0]-x)
    delta = (bearing-math.radians(t.rotation.yaw)+math.pi) % (2*math.pi)-math.pi
    speed = actor.get_velocity().length()
    desired = min(speed_target, max(0.0, (len(points)-index-1)*0.2))
    return carla.VehicleControl(throttle=max(0, min(.55, .3*(desired-speed))),
                                brake=max(0, min(.8, .45*(speed-desired))),
                                steer=max(-1, min(1, 1.5*delta))), index


def measure(actor):
    t = actor.get_transform()
    v = actor.get_velocity()
    vertices = [[p.x, p.y, p.z] for p in actor.bounding_box.get_world_vertices(t)]
    return {'actor_id': actor.id, 'position_m': [t.location.x, t.location.y, t.location.z],
            'heading_deg': t.rotation.yaw, 'speed_mps': math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z),
            'body_vertices_m': vertices, 'inside_crossing': inside_crossing(vertices)}


def image_for_frame(q, frame):
    image = q.get(timeout=30)
    while image.frame < frame:
        image = q.get(timeout=30)
    if image.frame != frame:
        raise RuntimeError('Camera/source frame mismatch')
    return image


def run(args):
    import carla  # Import only after explicit live request.
    from pipeline_capture import PipelineCapture
    cfg = config()
    case = cfg['case']
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'participants.jsonl').exists():
        raise ValueError('Retain prior attempt in its own directory')
    if not (output / 'config.json').exists():
        (output / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    client = carla.Client(args.host, args.port)
    client.set_timeout(90)
    if client.get_client_version() != client.get_server_version():
        raise RuntimeError('CARLA client/server version mismatch')
    old_world = client.get_world()
    old_map_name = old_world.get_map().name
    old_settings = old_world.get_settings()
    old_weather = old_world.get_weather()
    world = None
    actors = []
    cameras = []
    encoders = []
    capture = None
    channels = {}
    samples = []
    completed = False
    error = None
    try:
        world = client.generate_opendrive_world(build_xodr())
        setting = world.get_settings()
        setting.synchronous_mode = True
        setting.fixed_delta_seconds = .05
        world.apply_settings(setting)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        bp = world.get_blueprint_library().find('vehicle.tesla.model3')
        bp.set_attribute('role_name', 'ego')
        ego = world.spawn_actor(bp, carla.Transform(carla.Location(x=176, y=-3.5, z=.5)))
        actors.append(ego)
        bp_other = world.get_blueprint_library().find('vehicle.tesla.model3')
        bp_other.set_attribute('role_name', 'other')
        other = world.spawn_actor(bp_other, carla.Transform(carla.Location(x=203.5, y=-20, z=.5), carla.Rotation(yaw=90)))
        actors.append(other)
        for i, spec in enumerate(cfg['cameras']):
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', str(spec['width']))
            camera_bp.set_attribute('image_size_y', str(spec['height']))
            camera_bp.set_attribute('sensor_tick', '0')
            pose = carla.Transform(carla.Location(x=spec['location'][0], y=spec['location'][1], z=spec['location'][2]),
                                   carla.Rotation(pitch=spec['pitch']))
            sensor = world.spawn_actor(camera_bp, pose, attach_to=ego)
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
        channels = {item['name']: (output / 'channels' / (item['name'] + '.jsonl')).open('x')
                    for item in case['recording_description']['channels']}
        (output / 'context.json').write_text(json.dumps({'synthetic': cfg['authored_test_context'],
            'physical_geometry': 'road.xodr and original capture; no official device authored'}, indent=2) + '\n')
        start = world.get_snapshot().timestamp.elapsed_seconds
        other_entered = False
        with (output / 'participants.jsonl').open('x') as raw, (output / 'video_frames.jsonl').open('x') as frames:
            for i in range(cfg['max_ticks']):
                pre_other = measure(other)
                pre_ego = measure(ego)
                other_entered |= pre_other['inside_crossing']
                release_delay_s = case['variable_assignments']['commanded_release_delay_s']['value']
                # Frozen controller release is an input. The measured entry
                # difference is the observable, with no legal time cutoff.
                should_yield = False
                ego_control, ego_index = control(carla, ego, route('ego'), 0 if i*.05 < release_delay_s else 8)
                other_control, other_index = control(carla, other, route('other'), 3)
                ego.apply_control(ego_control)
                other.apply_control(other_control)
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - start
                ego_state, other_state = measure(ego), measure(other)
                sample = {'frame': frame, 'time_s': now, 'ego': ego_state, 'other': other_state,
                          'controller': {'release_delay_s': release_delay_s, 'ego_index': ego_index,
                                         'other_index': other_index}}
                samples.append(sample)
                raw.write(json.dumps(sample) + '\n')
                capture.capture(frame, now, extra={'crossing_capability_sample': sample})
                event = json.loads(evidence_reader.readline())
                if event['original_frame'] != frame:
                    raise RuntimeError('Original observation/source frame mismatch')
                for name, stream in channels.items():
                    stream.write(json.dumps({'time_s': now, 'value': {
                        'original_observations': event['original_observations'],
                        'physical_sample': sample}}) + '\n')
                source_frames = {}
                for (sensor, q), (encoder, _) in zip(cameras, encoders):
                    image = image_for_frame(q, frame)
                    raw_pixels = bytes(image.raw_data)
                    encoder.stdin.write(raw_pixels)
                    source_frames[str(sensor.id)] = {'native_frame': image.frame,
                        'source_bgra_sha256': hashlib.sha256(raw_pixels).hexdigest(),
                        'width': image.width, 'height': image.height}
                frames.write(json.dumps({'video_frame': i, 'native_frame': frame, 'time_s': now,
                    'source_frames': source_frames}) + '\n')
                if ego_index >= len(route('ego'))-2 and other_index >= len(route('other'))-2:
                    completed = True
                    break
    except BaseException as exc:
        error = repr(exc)
    finally:
        if 'evidence_reader' in locals():
            evidence_reader.close()
        for stream in channels.values():
            stream.close()
        if capture:
            capture.close(confirmed=completed and error is None)
        for encoder, log in encoders:
            encoder.stdin.close()
            encoder.wait(timeout=120)
            log.close()
        for actor in reversed(actors):
            actor.destroy()
        if world is not None:
            client.load_world(old_map_name)
            restored = client.get_world()
            restored.apply_settings(old_settings)
            restored.set_weather(old_weather)
    (output / 'capability-run.json').write_text(json.dumps({'case_id': case['case_id'],
        'frames': len(samples), 'completed': completed, 'error': error, 'physical_acceptance': False,
        'required_saved_review': ['native junction/road crossing', 'full footprint entry brackets',
                                  'decoded video counts and pixels', 'mandatory channel completeness']}, indent=2) + '\n')
    if error or not completed:
        raise RuntimeError('Capability run incomplete; inspect retained output')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check:
        check()
    else:
        if not (args.output_dir and args.host and args.port):
            parser.error('Live run requires output-dir, host, port')
        run(args)
