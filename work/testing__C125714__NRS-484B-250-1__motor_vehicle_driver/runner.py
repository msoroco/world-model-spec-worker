"""Configuration-driven native capability capture for partition-02 assignments."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from scene_model import build_xodr, route

ROOT = Path(__file__).resolve().parent


def check():
    config = json.loads((ROOT / 'config.json').read_text())
    case = config['case']
    assert case['case_id'] == config['selected_case_id']
    assert config['mode'] in ('crossing_priority', 'divider_turn', 'oneway', 'speed', 'signal')
    assert (ROOT / 'scene.xodr').read_text() == build_xodr(config['mode'])
    root = ET.parse(ROOT / 'scene.xodr').getroot()
    assert root.tag == 'OpenDRIVE' and root.findall('road')
    assert root.find('road[@id="1"]/lanes/laneSection/right/lane[@id="-1"]') is not None
    points = route(config['mode'], case)
    assert len(points) > 200 and len({tuple(p) for p in points}) == len(points)
    if config['mode'] in ('crossing_priority', 'speed'):
        assert len(route(config['mode'], case, other=True)) > 200
    if config['mode'] == 'divider_turn':
        assert root.find('junction[@id="100"]') is not None
        assert config['divider']['opening_x_m'] == [-12, 12]
    if config['mode'] == 'crossing_priority':
        assert root.find('junction[@id="101"]') is not None
        assert root.find('junction[@id="102"]') is not None
        assert config['crossing']['highway_road_ids'] == [1, 5]
    assert len(config['cameras']) == 4
    assert (config['cameras'][0]['width'], config['cameras'][0]['height']) == (1920, 1080)
    assert all((c['width'], c['height']) == (1280, 720) for c in config['cameras'][1:])
    names = {c['name'] for c in case['recording_description']['channels']}
    assert set(config['required_atoms']) <= names
    assert set(config['source_terms']) <= names
    print(json.dumps({'case_id': case['case_id'], 'mode': config['mode'],
                      'offline_check': 'passed', 'simulator_connected': False}))


def control(carla, vehicle, points, speed_target):
    transform = vehicle.get_transform()
    x, y = transform.location.x, transform.location.y
    nearest = min(range(len(points)), key=lambda i: (points[i][0]-x)**2 + (points[i][1]-y)**2)
    target = points[min(nearest + 12, len(points)-1)]
    heading = math.atan2(target[1]-y, target[0]-x)
    error = (heading - math.radians(transform.rotation.yaw) + math.pi) % (2*math.pi) - math.pi
    speed = vehicle.get_velocity().length()
    desired = min(speed_target, max(.5, (len(points)-1-nearest)*.08))
    return carla.VehicleControl(throttle=max(0, min(.55, .27*(desired-speed))),
                                brake=max(0, min(.8, .38*(speed-desired))),
                                steer=max(-1, min(1, 1.5*error))), nearest


def actor_sample(actor):
    tr = actor.get_transform()
    velocity = actor.get_velocity()
    return {'actor_id': actor.id, 'type_id': actor.type_id,
            'position_m': [tr.location.x, tr.location.y, tr.location.z],
            'heading_deg': tr.rotation.yaw,
            'velocity_mps': [velocity.x, velocity.y, velocity.z],
            'speed_mps': velocity.length(),
            'light_bits': int(actor.get_light_state()),
            'body_vertices_m': [[v.x, v.y, v.z] for v in actor.bounding_box.get_world_vertices(tr)]}


def channel_value(term, row, evidence, ego, other, world, frame, route_index, path_length, environment):
    if term == 'kin.position': return row['position_m']
    if term == 'kin.heading': return row['heading_deg']
    if term == 'kin.speed': return row['speed_mps']
    if term == 'kin.velocity': return ego['velocity_mps']
    if term == 'kin.path_length': return path_length
    if term == 'sig.turn_indicator':
        return {'frame': frame, 'api_light_bits': ego['light_bits'],
                'source': 'original actor.get_light_state; rendered right lamp requires later pixel review'}
    if term == 'sig.hand_signal':
        return {'frame': frame, 'observed': False, 'reason': 'No native arm-signal acquisition; alternate lamp branch only'}
    if term == 'env.precipitation': return world.get_weather().precipitation
    if term == 'env.wet_road': return world.get_weather().wetness
    if term in ('env.visibility', 'env.ice_or_snow'):
        return {'frame': frame, 'value': environment.get(term),
                'source': environment.get('source'), 'verified': environment.get(term) is not None}
    if term.startswith('st.') or term.startswith('dev.'):
        return {'frame': frame, 'native_projection': evidence['world'].get('road_projection'),
                'map_context': evidence['original_observations'].get('map_context'),
                'road_xodr_reference': 'road.xodr', 'native_inventory_reference': 'native-inventory.json',
                'specific_term': term, 'administrative_authority_confirmed': False}
    if term.startswith('rel.'):
        return {'frame': frame, 'ego': ego, 'other': other,
                'source': 'original same-frame actor bodies and native lane projection'}
    if term.startswith('drv.'):
        return {'frame': frame, 'ego': ego, 'other': other,
                'route_index': route_index, 'path_length_m': path_length,
                'source': 'original actor pose/control and authored route; legal predicate unresolved'}
    raise ValueError('No acquisition for legal term: ' + term)


def cleanup_action(errors, name, operation):
    try:
        return operation()
    except Exception as exc:
        errors.append(name + ': ' + repr(exc))


def run(args):
    import carla  # delayed; --check and tests are CPU only
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    config = json.loads((ROOT / 'config.json').read_text())
    case = config['case']
    mode = config['mode']
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'trace.jsonl').exists() or (output / 'video_frames.jsonl').exists():
        raise ValueError('Original evidence is immutable; choose a fresh attempt')
    if not (output / 'config.json').exists():
        (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(args.host, args.port)
    client.set_timeout(120)
    saved_world = snapshot(client)
    owned, encoders, channels = [], [], {}
    capture = None
    capture_complete = False
    try:
        world = client.generate_opendrive_world((ROOT / 'scene.xodr').read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        native_map = world.get_map()
        (output / 'road.xodr').write_text(native_map.to_opendrive())
        inventory = {'map_name': native_map.name, 'native_objects': list(world.get_names_of_all_objects()),
                     'topology': [{'from': [a.road_id, a.lane_id], 'to': [b.road_id, b.lane_id]}
                                  for a, b in native_map.get_topology()],
                     'administrative_dedication_verified': False}
        (output / 'native-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
        path = route(mode, case)
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'ego')
        yaw = 180 if mode == 'oneway' and case['variable_assignments']['direction']['value'] == 'opposite' else 0
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=path[0][0], y=path[0][1], z=.5), carla.Rotation(yaw=yaw)))
        owned.append(ego)
        other = None
        other_path = None
        if mode in ('crossing_priority', 'speed'):
            other_path = route(mode, case, other=True)
            second = world.get_blueprint_library().find('vehicle.tesla.model3')
            second.set_attribute('role_name', 'other')
            other = world.spawn_actor(second, carla.Transform(
                carla.Location(x=other_path[0][0], y=other_path[0][1], z=.5),
                carla.Rotation(yaw=90 if mode == 'crossing_priority' else 0)))
            owned.append(other)
        environment = {'env.visibility': None, 'env.ice_or_snow': None,
                       'source': 'native inventory and pre-recording calibration required'}
        if mode == 'speed' and other is not None:
            from worker_exchange.environment_acquisition import calibrate, fields
            calibration = calibrate(world, other, output, owned)
            environment['env.visibility'] = calibration['visibility_m']
            environment['source'] = 'environment_calibration.json; finite RGB/instance contrast range'
            inventory['material_asset_paths'] = []
            inventory['surface_limitation'] = 'Generated road material paths and ice appearance are not verified by the native object-name API'
            (output / 'native-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
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
            log = (output / ('view%d.encoder.log' % i)).open('x')
            proc = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', '%dx%d' % (spec['width'], spec['height']),
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgr0',
                str(output / ('view%d.mkv' % i))], stdin=subprocess.PIPE, stderr=log)
            cameras.append((sensor, frames))
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
        prior = None
        path_length = 0.0
        reversing_ticks = 0
        reverse_completed = False
        with (output / 'capture/evidence.jsonl').open() as evidence_stream, \
                (output / 'physical_samples.jsonl').open('x') as samples, \
                FrameMap(output / 'video_frames.jsonl') as frame_map:
            for tick in range(config['max_ticks']):
                if mode == 'signal':
                    remaining = max(0.0, -10 - ego.get_transform().location.x)
                    onset_m = case['variable_assignments']['signal_onset_ft']['value'] * .3048
                    ego.set_light_state(carla.VehicleLightState.RightBlinker if remaining <= onset_m else carla.VehicleLightState.NONE)
                delay = case['variable_assignments'].get('ego_delay_s', {}).get('value', 0)
                command, route_index = control(carla, ego, path, config['target_speed_mps'])
                if mode == 'divider_turn' and case['variable_assignments']['path_kind']['value'] == 'opening_multiple':
                    if not reverse_completed and reversing_ticks == 0 and ego.get_transform().location.x >= -20:
                        reversing_ticks = 25
                    if reversing_ticks > 0:
                        command = carla.VehicleControl(throttle=.22, reverse=True, steer=0)
                        reversing_ticks -= 1
                        if reversing_ticks == 0:
                            reverse_completed = True
                if tick * .05 < delay:
                    command = carla.VehicleControl(brake=1)
                if mode == 'crossing_priority' and case['variable_assignments'].get('yield_command', {}).get('value'):
                    x = ego.get_transform().location.x
                    other_y = other.get_transform().location.y if other is not None else -100
                    if -22 < x < -8 and -20 < other_y < 10:
                        command = carla.VehicleControl(brake=1)
                ego.apply_control(command)
                if other is not None:
                    other_command, _ = control(carla, other, other_path, config['other_speed_mps'])
                    other.apply_control(other_command)
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - start
                extra = {}
                if mode == 'speed':
                    from worker_exchange.environment_acquisition import fields
                    weather = fields(world.get_weather())
                    if weather != calibration['weather']:
                        raise RuntimeError('Weather changed since original optical calibration')
                    extra['environment_measurements'] = {'frame': frame, 'time_s': now,
                        'weather': weather, 'visibility_m': environment['env.visibility'],
                        'ice_or_snow': None, 'calibration_reference': 'environment_calibration.json',
                        'surface_reference': 'native-inventory.json'}
                row = capture.capture(frame, now, extra=extra)
                event = json.loads(evidence_stream.readline())
                if event['original_frame'] != frame:
                    raise RuntimeError('Original capture/evidence frame mismatch')
                ego_state = actor_sample(ego)
                other_state = actor_sample(other) if other is not None else None
                current = ego_state['position_m']
                if prior is not None:
                    path_length += math.dist(current, prior)
                prior = current
                samples.write(json.dumps({'frame': frame, 'time_s': now,
                    'ego': ego_state, 'other': other_state, 'route_index': route_index,
                    'path_length_m': path_length, 'applied_control': row['control']}) + '\n')
                for name, stream in channels.items():
                    value = channel_value(name, row, event, ego_state, other_state, world,
                                          frame, route_index, path_length, environment)
                    stream.write(json.dumps({'time_s': now, 'value': value}) + '\n')
                source_frames = {}
                for i, (_, frames) in enumerate(cameras):
                    image = frames.get(timeout=45)
                    while image.frame < frame:
                        image = frames.get(timeout=45)
                    if image.frame != frame:
                        raise RuntimeError('Original camera frame mismatch')
                    raw = bytes(image.raw_data)
                    encoders[i][0].stdin.write(raw)
                    source_frames['view%d' % i] = {'width': image.width, 'height': image.height,
                        'source_bgra_sha256': hashlib.sha256(raw).hexdigest()}
                frame_map.append(frame, now, source_frames=source_frames)
                if route_index >= len(path)-1 and row['speed_mps'] < 2:
                    break
        capture_complete = True
    finally:
        errors = []
        for stream in channels.values():
            cleanup_action(errors, 'channel close', stream.close)
        if capture is not None:
            cleanup_action(errors, 'capture close', lambda: capture.close(confirmed=capture_complete))
        for proc, log in encoders:
            cleanup_action(errors, 'encoder stdin close', proc.stdin.close)
            cleanup_action(errors, 'encoder wait', lambda proc=proc: proc.wait(timeout=120))
            cleanup_action(errors, 'encoder log close', log.close)
        for actor in reversed(owned):
            if actor.type_id.startswith('sensor.'):
                cleanup_action(errors, 'sensor stop', actor.stop)
            cleanup_action(errors, 'actor destroy', actor.destroy)
        def restore_world():
            receipt = restore(client, saved_world)
            (output / 'world-restore.json').write_text(json.dumps(receipt, indent=2) + '\n')
        cleanup_action(errors, 'world restore', restore_world)
        if errors:
            (output / 'cleanup-failures.json').write_text(json.dumps(errors, indent=2) + '\n')
            raise RuntimeError('; '.join(errors))


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
            parser.error('Capture requires --output-dir, --host, and --port')
        run(args)
