"""Two-directional intersection left-turn capability capture for NRS 484B.400(2)(a)."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def route(lateral):
    """Eastbound right half (south), then northbound right half (east)."""
    approach = [(-75 + i * .5, -lateral) for i in range(128)]
    p0, p1, p2, p3 = (-11, -lateral), (-2, -lateral), (lateral, 2), (lateral, 11)
    curve = []
    for i in range(1, 81):
        t = i / 80
        u = 1 - t
        curve.append((u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                      u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]))
    depart = [(lateral, 11 + i * .5) for i in range(1, 130)]
    return approach + curve + depart


def check():
    config = json.loads((ROOT / 'config.json').read_text())
    case = config['case']
    assert case['case_id'] == config['selected_case_id']
    assert config['law_id'] == 'NRS-484B-400-2a'
    lateral = case['variable_assignments']['approach_lateral_m']['value']
    assert lateral in (1.75, 5.25)
    points = route(lateral)
    assert points[0][0] < -70 and points[-1][1] > 70
    assert points[0][1] == -lateral and points[-1][0] == lateral
    assert all(-7 <= y <= 7 or -7 <= x <= 7 for x, y in points)
    root = ET.parse(ROOT / 'intersection.xodr').getroot()
    assert root.tag == 'OpenDRIVE'
    assert len(root.findall('road')) >= 5
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
        world = client.generate_opendrive_world((ROOT / 'intersection.xodr').read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        topology = [{'from': [a.road_id, a.lane_id], 'to': [b.road_id, b.lane_id]}
                    for a, b in mapping.get_topology()]
        (output / 'native-topology.json').write_text(json.dumps({'edges': topology}, indent=2) + '\n')
        lateral = case['variable_assignments']['approach_lateral_m']['value']
        points = route(lateral)
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'ego')
        ego = world.spawn_actor(blueprint, carla.Transform(carla.Location(x=points[0][0], y=points[0][1], z=.5)))
        owned.append(ego)
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
            for _ in range(config['max_ticks']):
                command, index = controller(carla, ego, points, config['target_speed_mps'])
                ego.apply_control(command)
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
                values = {'kin.position': original['position_m'], 'kin.heading': original['heading_deg'],
                    'kin.speed': original['speed_mps'],
                    'road_geometry': {'projection': packet['world']['road_projection'],
                        'map_context': packet['original_observations'].get('map_context'),
                        'native_topology_reference': 'native-topology.json'},
                    'turn_history': {'route_index': index, 'heading_deg': original['heading_deg'],
                        'position_m': original['position_m']}}
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
