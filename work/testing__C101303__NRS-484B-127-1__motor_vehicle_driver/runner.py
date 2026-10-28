"""Native capability capture for four exact partition-04 law/cell scenarios."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def route(lateral, mode='left_turn', exit_offset=None):
    """Controller route, with explicit mode-specific terminal geometry."""
    if mode == 'lane_change':
        points = []
        for i in range(301):
            x = -75 + i * .5
            t = max(0., min(1., (x + 25) / 30))
            ease = t*t*(3-2*t)
            points.append((x, -1.75 - 3.5*ease))
        return points
    if mode in ('signal_amber', 'signal_dark'):
        return [(-75 + i * .5, -1.75) for i in range(133)]
    if mode == 'winter_follow':
        points = []
        for i in range(301):
            x = -75 + i * .5
            t = max(0., min(1., (x - 15.) / 30.))
            ease = t*t*(3.-2.*t)
            points.append((x, -1.75 - 3.5*ease))
        return points
    if mode == 'signed_speed':
        return [(-75 + i * .5, -1.75) for i in range(301)]
    # Eastbound right half (south), then northbound right half (east).
    approach = [(-75 + i * .5, -lateral) for i in range(128)]
    exit_offset = lateral if exit_offset is None else exit_offset
    p0, p1, p2, p3 = (-11, -lateral), (-2, -lateral), (exit_offset, 2), (exit_offset, 11)
    curve = []
    for i in range(1, 81):
        t = i / 80
        u = 1 - t
        curve.append((u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                      u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]))
    depart = [(exit_offset, 11 + i * .5) for i in range(1, 130)]
    return approach + curve + depart


def check():
    config = json.loads((ROOT / 'config.json').read_text())
    case = config['case']
    assert case['case_id'] == config['selected_case_id']
    mode = config['mode']
    assert mode in ('winter_follow', 'signed_speed', 'signal_amber', 'signal_dark')
    lateral = case['variable_assignments'].get('approach_lateral_m', {}).get('value', 1.75)
    points = route(lateral, mode, case['variable_assignments'].get('exit_right_offset_m', {}).get('value'))
    assert points[0][0] < -70
    if mode in ('left_turn', 'yield_turn'):
        assert points[-1][1] > 70
        assert points[0][1] == -lateral
        assert all(-7 <= y <= 7 or -7 <= x <= 7 for x, y in points)
    else:
        assert points[-1][0] > (-10 if mode in ('signal_amber','signal_dark') else 70)
        if mode == 'winter_follow':
            assert points[0][1] == -1.75 and points[-1][1] == -5.25
            assert all(y == -1.75 for x,y in points if x < 15)
    root = ET.parse(ROOT / 'scene.xodr').getroot()
    assert root.tag == 'OpenDRIVE'
    assert len(root.findall('road')) >= (5 if mode in ('signal_amber', 'signal_dark') else 1)
    if mode in ('signal_amber', 'signal_dark'):
        assert root.find('road[@id="13"]/planView/geometry/arc') is not None
    for road in root.findall('road')[:4]:
        assert road.find('lanes/laneSection/left/lane[@id="1"]') is not None
        assert road.find('lanes/laneSection/right/lane[@id="-1"]') is not None
    assert len(config['cameras']) == 4
    assert (config['cameras'][0]['width'], config['cameras'][0]['height']) == (1920, 1080)
    assert all((c['width'], c['height']) == (1280, 720) for c in config['cameras'][1:])
    assert set(config['required_atoms']) <= {c['name'] for c in case['recording_description']['channels']}
    print(json.dumps({'case_id': case['case_id'], 'offline_check': 'passed',
                      'route_points': len(points), 'simulator_connected': False}))


def controller(carla, vehicle, points, speed_target):
    tr = vehicle.get_transform()
    x, y = tr.location.x, tr.location.y
    nearest = min(range(len(points)), key=lambda i: (points[i][0]-x)**2 + (points[i][1]-y)**2)
    target = points[min(nearest + 12, len(points)-1)]
    heading = math.atan2(target[1]-y, target[0]-x)
    error = (heading - math.radians(tr.rotation.yaw) + math.pi) % (2*math.pi) - math.pi
    speed = vehicle.get_velocity().length()
    desired = min(speed_target, max(.8, (len(points)-1-nearest)*.08))
    return carla.VehicleControl(throttle=max(0, min(.55, .25*(desired-speed))),
                                brake=max(0, min(.7, .35*(speed-desired))),
                                steer=max(-1, min(1, 1.5*error))), nearest


def capture_frame(mapping, frame, time_s, source_frames):
    return mapping.append(frame, time_s, source_frames=source_frames)


def cleanup_action(failures, label, action):
    try:
        return action()
    except Exception as exc:
        failures.append(label + ': ' + repr(exc))


def run(args):
    import carla  # lazy; --check and unit tests never connect
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    config = json.loads((ROOT / 'config.json').read_text())
    case = config['case']
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'trace.jsonl').exists() or (output / 'video_frames.jsonl').exists():
        raise ValueError('Use a fresh attempt directory; original evidence is immutable')
    if not (output / 'config.json').exists():
        (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(args.host, args.port)
    client.set_timeout(120)
    saved = snapshot(client)
    owned = []
    encoders = []
    channels = {}
    capture = None
    capture_complete = False
    try:
        world = client.generate_opendrive_world((ROOT / 'scene.xodr').read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.WetNoon if config['mode']=='winter_follow' and config['case']['variable_assignments']['weather_surface']['value']=='wet' else carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        topology = [{'from': [a.road_id, a.lane_id], 'to': [b.road_id, b.lane_id]}
                    for a, b in mapping.get_topology()]
        (output / 'native-topology.json').write_text(json.dumps({'edges': topology}, indent=2) + '\n')
        landmarks = []
        for landmark in mapping.get_all_landmarks():
            landmarks.append({'id': landmark.id, 'type': landmark.type,
                              'road_id': landmark.road_id, 's_m': landmark.s, 't_m': landmark.t})
        controls = {'landmarks': landmarks,
            'crosswalk_vertices_m': [[p.x, p.y, p.z] for p in mapping.get_crosswalks()],
            'native_object_names': list(world.get_names_of_all_objects()),
            'actor_inventory': [{'id': a.id, 'type_id': a.type_id} for a in world.get_actors()],
            'scope': 'native metadata inventory before original recording; rendered appearance still unverified',
            'traffic_light_actors': [{'id': a.id, 'state': str(a.get_state()), 'transform': str(a.get_transform())} for a in world.get_actors().filter('traffic.traffic_light*')]}
        (output / 'native-controls.json').write_text(json.dumps(controls, indent=2) + '\n')
        mode = config['mode']
        lateral = case['variable_assignments'].get('approach_lateral_m', {}).get('value', 1.75)
        points = route(lateral, mode, case['variable_assignments'].get('exit_right_offset_m', {}).get('value'))
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'ego')
        ego = world.spawn_actor(blueprint, carla.Transform(carla.Location(x=points[0][0], y=points[0][1], z=.5)))
        owned.append(ego)
        other = None
        if mode in ('winter_follow', 'signal_dark'):
            other_bp = world.get_blueprint_library().find('vehicle.tesla.model3')
            other_bp.set_attribute('role_name', 'other')
            other_x = 12 if mode == 'signal_dark' else -42
            other_y = 1.75 if mode == 'signal_dark' else -1.75
            other = world.spawn_actor(other_bp, carla.Transform(carla.Location(x=other_x, y=other_y, z=.5),
                                  carla.Rotation(yaw=180 if mode == 'signal_dark' else 0)))
            owned.append(other)
        cameras = []
        for i, spec in enumerate(config['cameras']):
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(spec['width']))
            bp.set_attribute('image_size_y', str(spec['height']))
            bp.set_attribute('sensor_tick', '0')
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=spec['x'], y=spec['y'], z=spec['z']),
                carla.Rotation(pitch=spec['pitch'], yaw=spec['yaw'])), attach_to=ego)
            owned.append(sensor)
            frames = queue.Queue()
            sensor.listen(frames.put)
            log = (output / ('view%d.ffmpeg.log' % i)).open('x')
            proc = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', '%dx%d' % (spec['width'], spec['height']),
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgr0',
                str(output / ('view%d.mkv' % i))], stdin=subprocess.PIPE, stderr=log)
            cameras.append((sensor, frames, spec))
            encoders.append((proc, log))
        for _ in range(5):
            world.tick()
        capture = PipelineCapture(client, ego, output, case['case_id'],
                                  required_observations=config['required_atoms'])
        (output / 'context.json').write_text(json.dumps({'authored_context': config['authored_test_context']}, indent=2) + '\n')
        (output / 'channels').mkdir()
        for channel in case['recording_description']['channels']:
            channels[channel['name']] = (output / 'channels' / (channel['name'] + '.jsonl')).open('x')
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'capture/evidence.jsonl').open() as evidence, \
                (output / 'physical_samples.jsonl').open('x') as samples, \
                FrameMap(output / 'video_frames.jsonl') as frame_map:
            stop_ticks = 0
            for tick in range(config['max_ticks']):
                command, index = controller(carla, ego, points, case['variable_assignments'].get('target_speed_mps',{}).get('value',config['target_speed_mps']))
                wait_ticks = int(case['variable_assignments'].get('yield_wait_s', {}).get('value', 0)*20)
                if mode == 'signal_dark' and other is not None and \
                        (other.get_transform().location.x > -15 or tick < wait_ticks):
                    command = carla.VehicleControl(throttle=0, brake=.8, steer=0)
                if mode == 'signal_dark':
                    ego.set_light_state(carla.VehicleLightState.LeftBlinker)
                stop_target_ticks = int(case['variable_assignments'].get('stop_duration_s', {}).get('value', 1)*20)
                if mode in ('signal_amber','signal_dark') and ego.get_transform().location.x >= -20 and stop_ticks < stop_target_ticks:
                    command = carla.VehicleControl(throttle=0, brake=1, steer=0)
                    if ego.get_velocity().length() < .05:
                        stop_ticks += 1
                signal_x = -25 - case['variable_assignments'].get('signal_lead_m', {}).get('value', 15)
                if mode == 'lane_change' and ego.get_transform().location.x > signal_x:
                    ego.set_light_state(carla.VehicleLightState.LeftBlinker)
                if mode == 'winter_follow' and ego.get_transform().location.x >= 12:
                    ego.set_light_state(carla.VehicleLightState.LeftBlinker)
                if mode == 'winter_follow' and other is not None:
                    gap = other.get_transform().location.x - ego.get_transform().location.x
                    desired = case['variable_assignments'].get('commanded_gap_m',{}).get('value',20)
                    if gap < desired + 5:
                        command = carla.VehicleControl(throttle=0, brake=min(1., (desired+5-gap)*.1), steer=0)
                ego.apply_control(command)
                if other is not None:
                    if mode == 'signal_dark':
                        other.apply_control(carla.VehicleControl(throttle=.35))
                    elif mode == 'winter_follow':
                        other.apply_control(carla.VehicleControl(throttle=.2))
                    else:
                        other.apply_control(carla.VehicleControl(brake=1))
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - start
                original = capture.capture(frame, now)
                packet = json.loads(evidence.readline())
                if packet['original_frame'] != frame:
                    raise RuntimeError('Original capture/evidence frame mismatch')
                pose = ego.get_transform()
                body = [[p.x, p.y, p.z] for p in ego.bounding_box.get_world_vertices(pose)]
                samples.write(json.dumps({'frame': frame, 'time_s': now, 'route_index': index,
                    'position_m': original['position_m'], 'heading_deg': original['heading_deg'],
                    'speed_mps': original['speed_mps'], 'body_vertices_m': body}) + '\n')
                other_state = None
                if other is not None:
                    tr = other.get_transform()
                    other_state = {'actor_id': other.id, 'position_m': [tr.location.x, tr.location.y, tr.location.z],
                                   'speed_mps': other.get_velocity().length(), 'heading_deg': tr.rotation.yaw,
                                   'body_vertices_m': [[p.x, p.y, p.z] for p in other.bounding_box.get_world_vertices(tr)]}
                values = {'kin.position': original['position_m'], 'kin.heading': original['heading_deg'],
                    'kin.speed': original['speed_mps'],
                    'source_observations': {'mode': mode, 'route_index': index,
                        'ego_body_vertices_m': body, 'other': other_state,
                        'native_light_state': str(ego.get_light_state()),
                        'road_projection': packet['world']['road_projection'],
                        'native_observations': packet['original_observations'],
                        'native_topology_reference': 'native-topology.json',
                        'native_controls_reference': 'native-controls.json',
                        'weather_surface_context': case['variable_assignments'].get('weather_surface',{}).get('value'),
                        'traffic_light_states': [{'id': a.id, 'state': str(a.get_state())} for a in world.get_actors().filter('traffic.traffic_light*')],
                        'applied_control': original['control']}}
                for name, stream in channels.items():
                    stream.write(json.dumps({'time_s': now, 'value': values[name]}) + '\n')
                source_frames = {}
                for i, (_, frames, spec) in enumerate(cameras):
                    image = frames.get(timeout=45)
                    while image.frame < frame:
                        image = frames.get(timeout=45)
                    if image.frame != frame:
                        raise RuntimeError('Camera frame differs from original capture')
                    raw = bytes(image.raw_data)
                    encoders[i][0].stdin.write(raw)
                    source_frames['view%d' % i] = {'width': image.width, 'height': image.height,
                        'source_bgra_sha256': hashlib.sha256(raw).hexdigest()}
                capture_frame(frame_map, frame, now, source_frames)
                if index >= len(points)-1 and original['speed_mps'] < 2:
                    break
        capture_complete = True
    finally:
        failures = []
        for stream in channels.values():
            cleanup_action(failures, 'channel close', stream.close)
        if capture is not None:
            cleanup_action(failures, 'capture close', lambda: capture.close(confirmed=capture_complete))
        for proc, log in encoders:
            cleanup_action(failures, 'encoder stdin close', proc.stdin.close)
            cleanup_action(failures, 'encoder wait', lambda proc=proc: proc.wait(timeout=120))
            cleanup_action(failures, 'encoder log close', log.close)
        for actor in reversed(owned):
            if actor.type_id.startswith('sensor.'):
                cleanup_action(failures, 'sensor stop', actor.stop)
            cleanup_action(failures, 'actor destroy', actor.destroy)
        def restore_world():
            receipt = restore(client, saved)
            (output / 'world-restore.json').write_text(json.dumps(receipt, indent=2) + '\n')
        cleanup_action(failures, 'world restore', restore_world)
        if failures:
            (output / 'cleanup-failures.json').write_text(json.dumps(failures, indent=2) + '\n')
            raise RuntimeError('; '.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    arguments = parser.parse_args()
    if arguments.check:
        check()
    else:
        if not (arguments.output_dir and arguments.host and arguments.port):
            parser.error('Capture requires --output-dir, --host and --port')
        run(arguments)
