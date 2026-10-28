"""400(2)(a) two-directional intersection capability episode.

The offline check parses the authored map and route without importing CARLA.
The live path requires an operator-owned endpoint and retains original evidence.
"""
import argparse
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def route(lateral):
    # Eastbound traffic occupies the south/right half (negative world Y).
    # Northbound traffic occupies the east/right half (positive world X).
    points = [(-70.0 + i, -lateral) for i in range(59)]
    a, b, c, d = (-11.0, -lateral), (-4.0, -lateral), (lateral, 4.0), (lateral, 11.0)
    for i in range(1, 81):
        t = i / 80
        u = 1 - t
        points.append((u**3*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t**3*d[0],
                       u**3*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t**3*d[1]))
    points += [(lateral, 11.0 + i) for i in range(1, 55)]
    return points


def check():
    cfg = json.loads((ROOT / 'config.json').read_text())
    case = cfg['case']
    assert case['case_id'] == cfg['selected_case_id']
    assert cfg['law_id'] == 'NRS-484B-400-2a' and cfg['actor'] == 'motor_vehicle_driver'
    root = ET.parse(ROOT / 'intersection.xodr').getroot()
    assert root.tag == 'OpenDRIVE'
    roads = root.findall('road')
    assert len(roads) >= 4
    assert all(r.find('lanes/laneSection/left/lane[@id="1"]') is not None and
               r.find('lanes/laneSection/right/lane[@id="-1"]') is not None for r in roads[:4])
    turn = root.find('road[@id="13"]')
    assert turn is not None and turn.find('planView/geometry/arc') is not None
    assert len(root.findall('junction/connection[@connectingRoad="13"]/laneLink')) == 2
    geometry = turn.find('planView/geometry')
    curvature = float(geometry.find('arc').get('curvature'))
    angle = float(geometry.get('length')) * curvature
    end_x = float(geometry.get('x')) + math.sin(angle) / curvature
    end_y = float(geometry.get('y')) + (1 - math.cos(angle)) / curvature
    assert abs(end_x) < 0.01 and abs(end_y - 7) < 0.01 and abs(angle - math.pi/2) < 0.01
    assert not root.findall('.//signals/signal')
    lateral = case['variable_assignments']['commanded_approach_lateral']['value']
    assert lateral in (1.75, 5.25)
    path = route(lateral)
    assert len(path) > 150 and path[0][0] < -60 and path[-1][1] > 60
    assert path[0][1] == -lateral and path[-1][0] == lateral
    assert all(abs(y) <= 7 or abs(x) <= 7 for x, y in path)
    cameras = cfg['cameras']
    assert len(cameras) == 4
    assert (cameras[0]['width'], cameras[0]['height']) == (1920, 1080)
    assert all((c['width'], c['height']) == (1280, 720) for c in cameras[1:])
    required = {o['name'] for o in cfg['observations'] if o.get('mandatory', True)}
    assert required <= {c['name'] for c in case['recording_description']['channels']}
    print(json.dumps({'offline_check': 'passed', 'case_id': case['case_id'],
                      'route_points': len(path), 'simulator_connected': False}))


def control(carla, ego, points, target_speed):
    transform = ego.get_transform()
    x, y = transform.location.x, transform.location.y
    speed = ego.get_velocity().length()
    nearest = min(range(len(points)), key=lambda i: (points[i][0]-x)**2+(points[i][1]-y)**2)
    target = points[min(nearest + 8, len(points)-1)]
    angle = math.atan2(target[1]-y, target[0]-x)
    error = (angle - math.radians(transform.rotation.yaw) + math.pi) % (2*math.pi) - math.pi
    steer = max(-1.0, min(1.0, 1.8*error))
    desired = min(target_speed, max(1.5, (len(points)-1-nearest)*0.12))
    throttle = max(0.0, min(0.55, 0.3*(desired-speed)))
    brake = max(0.0, min(0.6, 0.35*(speed-desired)))
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer), nearest


def run(args):
    import carla  # lazy: offline checks never connect to a simulator
    import queue
    from pipeline_capture import PipelineCapture
    cfg = json.loads((ROOT / 'config.json').read_text())
    case = cfg['case']
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'physical_samples.jsonl').exists():
        raise ValueError('Retain the previous attempt; choose a fresh output directory')
    if not (out / 'config.json').exists():
        (out / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    client = carla.Client(args.host, args.port)
    client.set_timeout(120)
    original_world = client.get_world()
    original_map = original_world.get_map().name
    original_settings = original_world.get_settings()
    original_weather = original_world.get_weather()
    world = None
    actors = []
    capture = None
    encoders = {}
    logs = {}
    frames = 0
    success = False
    try:
        world = client.generate_opendrive_world((ROOT / 'intersection.xodr').read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        native_edges = [{'from': [a.road_id, a.lane_id], 'to': [b.road_id, b.lane_id]}
                        for a, b in mapping.get_topology()]
        (out / 'native-topology.json').write_text(json.dumps({'edges': native_edges}, indent=2) + '\n')
        lateral = case['variable_assignments']['commanded_approach_lateral']['value']
        points = route(lateral)
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'ego')
        ego = world.spawn_actor(blueprint, carla.Transform(carla.Location(x=points[0][0], y=points[0][1], z=0.5)))
        actors.append(ego)
        cameras = {}
        queues = {}
        for i, spec in enumerate(cfg['cameras']):
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(spec['width']))
            bp.set_attribute('image_size_y', str(spec['height']))
            bp.set_attribute('sensor_tick', '0')
            camera = world.spawn_actor(bp, carla.Transform(carla.Location(x=spec['x'], z=spec['z']),
                                                            carla.Rotation(pitch=spec['pitch'])), attach_to=ego)
            actors.append(camera)
            name = 'view%d' % i
            cameras[name] = camera
            queues[name] = queue.Queue()
            camera.listen(queues[name].put)
            logs[name] = (out / (name + '.ffmpeg.log')).open('x')
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', '%dx%d' % (spec['width'], spec['height']),
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'libvpx-vp9', '-lossless', '1',
                '-crf', '0', '-b:v', '0', '-pix_fmt', 'yuv444p', str(out / (name + '.webm'))],
                stdin=subprocess.PIPE, stderr=logs[name])
        for _ in range(5):
            world.tick()
        capture = PipelineCapture(client, ego, out, case['case_id'], required_observations=cfg['required_atoms'])
        (out / 'context.json').write_text(json.dumps(cfg['authored_test_context'], indent=2) + '\n')
        (out / 'channels').mkdir()
        channels = {c['name']: (out / 'channels' / (c['name'] + '.jsonl')).open('x')
                    for c in case['recording_description']['channels']}
        start = world.get_snapshot().timestamp.elapsed_seconds
        try:
            with (out / 'capture/evidence.jsonl').open() as evidence, \
                    (out / 'video_frames.jsonl').open('x') as mapping, \
                    (out / 'physical_samples.jsonl').open('x') as physical:
                for i in range(cfg['max_ticks']):
                    command, index = control(carla, ego, points, 5.0)
                    ego.apply_control(command)
                    frame = world.tick()
                    now = world.get_snapshot().timestamp.elapsed_seconds - start
                    row = capture.capture(frame, now)
                    event = json.loads(evidence.readline())
                    if event['original_frame'] != frame:
                        raise RuntimeError('Original observation/source frame mismatch')
                    t = ego.get_transform()
                    verts = [[v.x, v.y, v.z] for v in ego.bounding_box.get_world_vertices(t)]
                    sample = {'time_s': now, 'frame': frame, 'position_m': [t.location.x, t.location.y, t.location.z],
                              'speed_mps': row['speed_mps'], 'route_index': index, 'body_vertices_m': verts,
                              'applied_control': row['control']}
                    physical.write(json.dumps(sample) + '\n')
                    for name, stream in channels.items():
                        value = t.location.y if name == 'kin.position' else {
                            'source_frame': frame, 'native_original_observations': event['original_observations'],
                            'native_world': event['world'], 'ego_body_vertices_m': verts,
                            'geometry_source': 'road.xodr', 'legal_predicate_resolved': False}
                        stream.write(json.dumps({'time_s': now, 'value': value}) + '\n')
                    source_frames = {}
                    for name, camera in cameras.items():
                        image = queues[name].get(timeout=20)
                        while image.frame < frame:
                            image = queues[name].get(timeout=20)
                        if image.frame != frame:
                            raise RuntimeError('Camera/source frame mismatch')
                        raw = bytes(image.raw_data)
                        encoders[name].stdin.write(raw)
                        source_frames[name] = {'width': image.width, 'height': image.height,
                            'source_bgra_sha256': hashlib.sha256(raw).hexdigest()}
                    mapping.write(json.dumps({'video_frame': i, 'native_frame': frame,
                        'time_s': now, 'source_frames': source_frames}) + '\n')
                    frames += 1
                    if index == len(points)-1 and row['speed_mps'] < 2:
                        success = True
                        break
        finally:
            for stream in channels.values():
                stream.close()
        (out / 'capability-report.json').write_text(json.dumps({'case_id': case['case_id'],
            'recorded_frames': frames, 'route_completed': success, 'physical_acceptance': False,
            'unverified': ['native route continuity', 'approach footprint', 'camera visibility', 'duration']}, indent=2) + '\n')
    finally:
        if capture:
            capture.close(confirmed=success)
        for name, encoder in encoders.items():
            encoder.stdin.close()
            encoder.wait(timeout=120)
            logs[name].close()
        for actor in reversed(actors):
            actor.destroy()
        if world:
            client.load_world(original_map)
            restored = client.get_world()
            restored.apply_settings(original_settings)
            restored.set_weather(original_weather)
    if not success:
        raise RuntimeError('Native maneuver incomplete; inspect retained capability report')


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
        if not args.output_dir or not args.host or not args.port:
            parser.error('Live execution requires output-dir, host and port')
        run(args)
