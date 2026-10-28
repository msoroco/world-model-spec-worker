"""Median-opening U-turn capability capture with native surface survey."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from scenario import build_xodr, route, static_check, median_status

ROOT = Path(__file__).resolve().parent


def config():
    return json.loads((ROOT / 'config.json').read_text())


def check():
    cfg = config()
    case = cfg['case']
    assert cfg['law_id'] == 'NRS-484B-227-1'
    assert cfg['actor'] == 'motor_vehicle_driver'
    assert cfg['selected_case_id'] == case['case_id']
    assert case['variable_assignments']['test_branch']['value'] in ('u_turn_opening', 'u_turn_divider', 'u_turn_opening_multiple')
    assert len(cfg['cameras']) == 4
    assert (cfg['cameras'][0]['width'], cfg['cameras'][0]['height']) == (1920, 1080)
    assert all((c['width'], c['height']) == (1280, 720) for c in cfg['cameras'][1:])
    assert set(cfg['required_atoms']) <= {c['name'] for c in case['recording_description']['channels']}
    path = route(case)
    assert len(path) > 250
    assert all(math.dist(a,b) <= 1.5 for a,b in zip(path,path[1:]))
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


def run(args):
    import carla  # live path only
    from pipeline_capture import PipelineCapture
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
    old_world = client.get_world()
    old_map = old_world.get_map().name
    old_settings = old_world.get_settings()
    old_weather = old_world.get_weather()
    world = None
    actors, cameras, encoders = [], [], []
    channels = {}
    capture = None
    count = 0
    completed = False
    terminal_observed = False
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
        ego = world.spawn_actor(bp, carla.Transform(carla.Location(x=path[0][0], y=path[0][1], z=.5)))
        actors.append(ego)
        collision_events = []
        collision_bp = world.get_blueprint_library().find('sensor.other.collision')
        collision = world.spawn_actor(collision_bp, carla.Transform(), attach_to=ego)
        actors.append(collision)
        collision.listen(lambda event: collision_events.append({'frame': event.frame,
            'other_actor_id': event.other_actor.id,
            'impulse': [event.normal_impulse.x, event.normal_impulse.y, event.normal_impulse.z]}))
        rays = []
        for x, y in [(150,10),(185,10),(205,10),(225,10),(250,10),(205,-3.5),(205,23.5)]:
            hits = world.cast_ray(carla.Location(x=x,y=y,z=5),carla.Location(x=x,y=y,z=-5))
            rays.append({'xy_m':[x,y], 'hits':[{'label':str(h.label),
                'location_m':[h.location.x,h.location.y,h.location.z]} for h in hits]})
        native = {'map': world.get_map().name, 'synthetic_context': cfg['authored_test_context'],
                  'authored_divider_segments_x_m': [[0,190],[220,400]],
                  'authored_opening_x_m': [190,220],
                  'native_surface_rays': rays,
                  'native_static_props': [{'actor_id': a.id, 'type_id': a.type_id} for a in world.get_actors()
                                          if a.type_id.startswith('static.')],
                  'survey_limitation': 'Ray hits and native props must be reconciled with actual collision and original pixels; no setup acceptance here'}
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
        reverse_ticks = 0
        reverse_phase = 'approach'
        reverse_origin_x = None
        reversal_finished = False
        with (output / 'physical_samples.jsonl').open('x') as raw, (output / 'video_frames.jsonl').open('x') as mapping:
            for i in range(cfg['max_ticks']):
                request, index = control(carla, ego, path, 5)
                branch = case['variable_assignments']['test_branch']['value']
                if branch == 'u_turn_opening_multiple' and not reversal_finished:
                    position_x = ego.get_transform().location.x
                    speed = ego.get_velocity().length()
                    if reverse_phase == 'approach' and position_x >= 198:
                        reverse_phase = 'brake_before_reverse'
                    if reverse_phase == 'brake_before_reverse':
                        request = carla.VehicleControl(throttle=0, brake=1, steer=0)
                        if speed < .1:
                            reverse_origin_x = position_x
                            reverse_phase = 'reversing'
                    elif reverse_phase == 'reversing':
                        request = carla.VehicleControl(throttle=.3, brake=0, steer=0, reverse=True)
                        reverse_ticks += 1
                        if reverse_origin_x-position_x >= 1.5:
                            reversal_finished = True
                            reverse_phase = 'forward_again'
                        elif reverse_ticks > 100:
                            raise RuntimeError('Requested physical reverse displacement not achieved')
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
                          'body_vertices_m': vertices, 'route_index': index, 'control': row['control'],
                          'median_status': median_status(vertices),
                          'reverse_ticks': reverse_ticks, 'reverse_phase': reverse_phase,
                          'collision_events': list(collision_events)}
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
                mapping.write(json.dumps({'video_frame': i, 'native_frame': frame, 'time_s': now,
                                          'source_frames': source_frames}) + '\n')
                count += 1
                if collision_events:
                    terminal_observed = case['variable_assignments']['test_branch']['value'] == 'u_turn_divider'
                    break
                if index >= len(path)-2 and row['speed_mps'] < 2:
                    completed = True
                    terminal_observed = True
                    break
    except BaseException as exc:
        error = repr(exc)
    finally:
        for stream in channels.values():
            stream.close()
        if 'evidence_reader' in locals():
            evidence_reader.close()
        if capture:
            capture.close(confirmed=terminal_observed and error is None)
        for encoder, log in encoders:
            encoder.stdin.close()
            encoder.wait(timeout=120)
            log.close()
        for actor in reversed(actors):
            actor.destroy()
        if world is not None:
            client.load_world(old_map)
            restored = client.get_world()
            restored.apply_settings(old_settings)
            restored.set_weather(old_weather)
    (output / 'capability-run.json').write_text(json.dumps({'case_id': case['case_id'],
        'recorded_frames': count, 'route_completed': completed, 'error': error,
        'terminal_collision_observed': bool(collision_events) if 'collision_events' in locals() else False,
        'capability_terminal_observed': terminal_observed,
        'physical_acceptance': False, 'unverified': ['native divider and opening surface/collision',
        'full body median passage', 'reverse movement realization', 'public-authority status',
        'camera visibility', 'mandatory source coverage', 'final decoded videos']}, indent=2) + '\n')
    if error or not terminal_observed:
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
