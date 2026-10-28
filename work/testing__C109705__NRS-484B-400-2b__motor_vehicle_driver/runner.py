"""Partition 01 native capability episode for the selected exact case.

The offline check parses the authored map and route without importing CARLA.
The live path requires an operator-owned endpoint and retains original evidence.
"""
import argparse
import ast
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def left_route(lateral, exit_lateral=None):
    exit_lateral = lateral if exit_lateral is None else exit_lateral
    # Eastbound traffic occupies the south/right half (negative world Y).
    # Northbound traffic occupies the east/right half (positive world X).
    points = [(-70.0 + i, -lateral) for i in range(59)]
    a, b, c, d = (-11.0, -lateral), (-4.0, -lateral), (exit_lateral, 4.0), (exit_lateral, 11.0)
    for i in range(1, 81):
        t = i / 80
        u = 1 - t
        points.append((u**3*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t**3*d[0],
                       u**3*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t**3*d[1]))
    points += [(exit_lateral, 11.0 + i) for i in range(1, 55)]
    return points


def route(cfg):
    values = cfg['case']['variable_assignments']
    law = cfg['law_id']
    if law.endswith(('400-2b', '253')):
        lateral = values.get('commanded_approach_lateral', {}).get('value', 1.75)
        exit_lateral = values.get('commanded_exit_lateral', {}).get('value', 1.75)
        return left_route(lateral, exit_lateral)
    if law.endswith('223-1b'):
        start = values.get('commanded_start_lateral', {}).get('value', 1.75)
        end = values.get('commanded_end_lateral', {}).get('value', 5.25)
        points = []
        for i in range(131):
            x = -70.0 + i
            t = max(0.0, min(1.0, (x + 25.0) / 30.0))
            points.append((x, -start-(end-start)*(3*t*t-2*t*t*t)))
        return points
    lateral = values.get('commanded_approach_lateral', {}).get('value', 1.75)
    return [(-70.0+i, -lateral) for i in range(131)]


def check():
    cfg = json.loads((ROOT / 'config.json').read_text())
    case = cfg['case']
    assert case['case_id'] == cfg['selected_case_id']
    assert cfg['law_id'] in ('NRS-484B-400-2b', 'NRS-484B-253', 'NRS-484B-223-1b',
                             'NRS-484B-127-3', 'NRS-484A-450-2')
    assert cfg['actor'] == 'motor_vehicle_driver'
    root = ET.parse(ROOT / 'intersection.xodr').getroot()
    assert root.tag == 'OpenDRIVE'
    roads = root.findall('road')
    assert len(roads) >= 4
    assert all(r.find('lanes/laneSection/left/lane[@id="1"]') is not None and
               r.find('lanes/laneSection/right/lane[@id="-1"]') is not None for r in roads[:4])
    if cfg['law_id'] == 'NRS-484A-450-2':
        assert root.findall('.//signals/signal')
        assert (ROOT/'markings.py').is_file()
        ast.parse((ROOT/'markings.py').read_text())
    else:
        assert not root.findall('.//signals/signal')
    if cfg['law_id'].endswith(('400-2b','253')):
        turn = next((r for r in roads if r.attrib.get('id') == '13'), None)
        assert turn is not None and turn.find('planView/geometry/arc') is not None
        assert any(c.attrib.get('connectingRoad') == '13' for c in root.findall('junction/connection'))
    path = route(cfg)
    assert len(path) > 120 and path[0][0] < -60
    assert all(max(abs(a[0]-b[0]),abs(a[1]-b[1])) <= 1.5 for a,b in zip(path,path[1:]))
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


def channel_value(name, sample, original):
    """Project measured original evidence, never a requested controller value."""
    if name == 'kin.speed':
        return sample['speed_mps']
    if name == 'kin.position':
        return sample['position_m']
    if name == 'sig.turn_indicator':
        return sample['light_state_bits']
    if name == 'drv.stopped':
        return sample['speed_mps']
    if name == 'rel.surface_gap':
        if not sample['participants']:
            return None
        other=sample['participants'][0]
        return min(v[0] for v in other['body_vertices_m'])-max(v[0] for v in sample['body_vertices_m'])
    if name == 'st.sight_distance':
        return original.get('visibility')
    if name in ('rel.visible','rel.oncoming','drv.time_to_conflict'):
        return original['original_observations'].get('relations',[])
    return {'sample':sample,'original_observations':original['original_observations'],
            'native_world_projection':original['world']}


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
    original_xodr = original_world.get_map().to_opendrive()
    available_map = next((m for m in client.get_available_maps()
        if m.rsplit('/',1)[-1] == original_map.rsplit('/',1)[-1]), None)
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
        points = route(cfg)
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'ego')
        ego = world.spawn_actor(blueprint, carla.Transform(carla.Location(x=points[0][0], y=points[0][1], z=0.5)))
        actors.append(ego)
        participants = {}
        if cfg['law_id'] == 'NRS-484B-253':
            other_bp=world.get_blueprint_library().find('vehicle.tesla.model3')
            other_bp.set_attribute('role_name','opposing')
            participants['opposing']=world.spawn_actor(other_bp,carla.Transform(carla.Location(x=70,y=1.75,z=.5),carla.Rotation(yaw=180)))
        elif cfg['law_id'] == 'NRS-484B-127-3':
            other_bp=world.get_blueprint_library().find('vehicle.tesla.model3')
            other_bp.set_attribute('role_name','caravan_leader')
            gap=case['variable_assignments'].get('commanded_gap',{}).get('value',20)
            participants['leader']=world.spawn_actor(other_bp,carla.Transform(carla.Location(x=points[0][0]+gap+5,y=points[0][1],z=.5)))
            other_bp.set_attribute('role_name','entrant')
            participants['entrant']=world.spawn_actor(other_bp,carla.Transform(carla.Location(x=points[0][0]+gap/2,y=-5.25,z=.5)))
        actors.extend(participants.values())
        if cfg['law_id'] == 'NRS-484A-450-2':
            from markings import spawn as spawn_crosswalk
            actors.extend(spawn_crosswalk(carla, world, False))
        setup={'native_map':world.get_map().name,
               'native_road_ids':[r.id for r in world.get_map().get_topology() for r in r],
               'stop_signs':[{'id':a.id,'type_id':a.type_id,
                 'position_m':[a.get_location().x,a.get_location().y,a.get_location().z]}
                 for a in world.get_actors().filter('traffic.stop*')],
               'crosswalk_tiles':[{'id':a.id,'role':a.attributes.get('role_name'),
                 'body_vertices_m':[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]}
                 for a in actors if a.attributes.get('role_name','').startswith('stop257_west_crosswalk')]}
        (out/'native_setup.json').write_text(json.dumps(setup,indent=2)+'\n')
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
        evidence_reader=(out/'capture/evidence.jsonl').open('r')
        (out / 'channels').mkdir()
        channels = {c['name']: (out / 'channels' / (c['name'] + '.jsonl')).open('x')
                    for c in case['recording_description']['channels']}
        start = world.get_snapshot().timestamp.elapsed_seconds
        halt_started = None
        try:
            with (out / 'video_frames.jsonl').open('x') as mapping, (out / 'physical_samples.jsonl').open('x') as physical:
                for i in range(cfg['max_ticks']):
                    command, index = control(carla, ego, points, 5.0)
                    if cfg['law_id'] == 'NRS-484A-450-2':
                        should_halt = case['variable_assignments']['commanded_halt']['value']
                        if should_halt and halt_started is None and -25 < ego.get_location().x < -10:
                            halt_started = i
                        if halt_started is not None and i-halt_started < 40:
                            command = carla.VehicleControl(brake=.85,steer=command.steer)
                    if cfg['law_id'] == 'NRS-484B-253':
                        opposing=participants['opposing']
                        if case['variable_assignments']['commanded_yield']['value'] and opposing.get_location().x > -8 and ego.get_location().x > -20:
                            command = carla.VehicleControl(brake=.8,steer=command.steer)
                    if cfg['law_id'] == 'NRS-484B-223-1b':
                        signal = case['variable_assignments']['commanded_signal']['value']
                        ego.set_light_state(carla.VehicleLightState.LeftBlinker if signal else carla.VehicleLightState.NONE)
                    ego.apply_control(command)
                    for role, other in participants.items():
                        if role == 'entrant':
                            entrant_route=[(points[0][0]+gap/2+j,
                                            -5.25+3.5*(3*t*t-2*t*t*t))
                                           for j in range(100)
                                           for t in [max(0,min(1,(j-15)/30))]]
                            other_command,_=control(carla,other,entrant_route,5.0)
                        else:
                            other_command=carla.VehicleControl(throttle=.25)
                        other.apply_control(other_command)
                    frame = world.tick()
                    now = world.get_snapshot().timestamp.elapsed_seconds - start
                    row = capture.capture(frame, now)
                    original=json.loads(evidence_reader.readline())
                    if original['original_frame'] != frame:
                        raise RuntimeError('Original observation/source frame mismatch')
                    t = ego.get_transform()
                    verts = [[v.x, v.y, v.z] for v in ego.bounding_box.get_world_vertices(t)]
                    sample = {'time_s': now, 'frame': frame, 'position_m': [t.location.x, t.location.y, t.location.z],
                              'speed_mps': row['speed_mps'], 'route_index': index, 'body_vertices_m': verts,
                              'applied_control': row['control'],
                              'participants': [{'id': a.id, 'type_id': a.type_id,
                                'position_m': [a.get_location().x,a.get_location().y,a.get_location().z],
                                'body_vertices_m': [[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]}
                                for a in participants.values()],
                              'light_state_bits': int(ego.get_light_state())}
                    physical.write(json.dumps(sample) + '\n')
                    for name, stream in channels.items():
                        value = channel_value(name,sample,original)
                        stream.write(json.dumps({'time_s': now, 'value': value}) + '\n')
                    for name, camera in cameras.items():
                        image = queues[name].get(timeout=20)
                        while image.frame < frame:
                            image = queues[name].get(timeout=20)
                        if image.frame != frame:
                            raise RuntimeError('Camera/source frame mismatch')
                        encoders[name].stdin.write(bytes(image.raw_data))
                    mapping.write(json.dumps({'video_frame': i, 'native_frame': frame, 'time_s': now}) + '\n')
                    frames += 1
                    if index >= len(points)-2 and row['speed_mps'] < 2:
                        success = True
                        break
        finally:
            for stream in channels.values():
                stream.close()
            evidence_reader.close()
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
            if available_map:
                client.load_world(available_map)
            else:
                client.generate_opendrive_world(original_xodr)
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
