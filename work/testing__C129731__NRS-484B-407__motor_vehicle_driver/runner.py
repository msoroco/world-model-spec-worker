"""Configuration-driven original capture for the partition-03 capability cases.

`--check` never imports CARLA or connects. The live path needs an operator-owned
server and keeps every original frame, actor observation, map and source video.
"""
import argparse
import hashlib
import json
import math
import queue
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CURVE_RADIUS_M = 300.0
TURN_STATION_M = 250.0
CURVE_LENGTH_M = 500.0


def sight_stations(probe_m):
    """Two actual road stations flanking the U-turn, never off-road XY guesses."""
    stations = (TURN_STATION_M - probe_m, TURN_STATION_M + probe_m)
    if not all(0 < station < CURVE_LENGTH_M for station in stations):
        raise ValueError('Sight probe exceeds authored roadway approaches')
    return stations


def read(path):
    return json.loads(Path(path).read_text())


def route(config, case, role='ego'):
    mode = config['mode']
    if mode in ('signed_yield', 'signed_non_through'):
        if role != 'ego':
            return [(0.0, -80.0 + i * .5) for i in range(321)]
        return [(-80.0 + i * .5, -1.75) for i in range(321)]
    if mode == 'curve_u_turn':
        # Follow the authored 1/90 m native curve to the reversal envelope.
        def lane_point(s, side):
            heading = s / CURVE_RADIUS_M
            centre_x = -100.0 + CURVE_RADIUS_M * math.sin(heading)
            centre_y = CURVE_RADIUS_M * (1.0 - math.cos(heading))
            return (centre_x + side * 1.75 * math.sin(heading),
                    centre_y - side * 1.75 * math.cos(heading))
        approach = [lane_point(165.0 + i * .5, 1) for i in range(171)]
        start, finish = approach[-1], lane_point(TURN_STATION_M, -1)
        middle = ((start[0] + finish[0]) / 2 + 3.5 * math.cos(TURN_STATION_M/CURVE_RADIUS_M),
                  (start[1] + finish[1]) / 2 + 3.5 * math.sin(TURN_STATION_M/CURVE_RADIUS_M))
        turn = []
        for i in range(1, 81):
            t = i / 80
            u = 1 - t
            turn.append((u*u*start[0] + 2*u*t*middle[0] + t*t*finish[0],
                         u*u*start[1] + 2*u*t*middle[1] + t*t*finish[1]))
        depart = [lane_point(TURN_STATION_M - i * .5, -1) for i in range(1, 171)]
        return approach + turn + depart
    if mode == 'truck_follow':
        start = case['variable_assignments']['requested_gap_m']['value'] + 12.0 if role != 'ego' else 0.0
        return [(start + i * .5, -1.75) for i in range(801)]
    if mode == 'reverse_crosswalk':
        end = case['variable_assignments']['reverse_endpoint_x_m']['value']
        count = int(round((20.0 - end) / .25))
        return [(20.0 - i * .25, -1.75) for i in range(count + 1)]
    raise ValueError('Unknown scene mode: ' + mode)


def check():
    config = read(ROOT / 'config.json')
    case = config['case']
    assert case['case_id'] == config['selected_case_id']
    assert config['mode'] in ('signed_yield', 'signed_non_through', 'curve_u_turn',
                              'truck_follow', 'reverse_crosswalk')
    root = ET.parse(ROOT / 'scene.xodr').getroot()
    assert root.tag == 'OpenDRIVE' and root.findall('road')
    if config['mode'] == 'curve_u_turn':
        road = root.find('road[@id="1"]')
        assert road is not None and float(road.get('length')) == CURVE_LENGTH_M
        assert road.find('planView/geometry/arc') is not None
        sight_stations(case['variable_assignments']['sight_probe_m']['value'])
    assert len(route(config, case)) >= 40
    cameras = config['cameras']
    assert len(cameras) == 4 and (cameras[0]['width'], cameras[0]['height']) == (1920, 1080)
    assert all((s['width'], s['height']) == (1280, 720) for s in cameras[1:])
    channels = {c['name'] for c in case['recording_description']['channels']}
    assert set(config['required_atoms']) <= channels
    # The pinned atom gate runs against the repository runtime before bundling;
    # a materialized exact case has no repository-relative runtime directory.
    print(json.dumps({'case_id': case['case_id'], 'offline_check': 'passed',
                      'mode': config['mode'], 'simulator_connected': False}))


def control(carla, vehicle, points, target_speed, reverse=False):
    pose = vehicle.get_transform()
    x, y = pose.location.x, pose.location.y
    nearest = min(range(len(points)), key=lambda i: (points[i][0]-x)**2 + (points[i][1]-y)**2)
    target = points[min(nearest + 12, len(points)-1)]
    heading = math.atan2(target[1]-y, target[0]-x)
    if reverse:
        heading = (heading + math.pi) % (2 * math.pi)
    error = (heading - math.radians(pose.rotation.yaw) + math.pi) % (2 * math.pi) - math.pi
    speed = vehicle.get_velocity().length()
    desired = min(target_speed, max(.45, (len(points)-1-nearest) * .06))
    return carla.VehicleControl(throttle=max(0, min(.45, .24 * (desired-speed))),
                                brake=max(0, min(.7, .35 * (speed-desired))),
                                steer=max(-1, min(1, (-1 if reverse else 1) * 1.5 * error)),
                                reverse=reverse), nearest


def cleanup_action(failures, label, action):
    try:
        return action()
    except Exception as exc:
        failures.append(label + ': ' + repr(exc))


def source_values(config, point, event, route_index, body, other, frame):
    """Project same-frame original evidence, retaining unknown legal judgments."""
    obs = event['original_observations']
    crosswalk = config.get('crosswalk_box_m', [-2.0, 2.0, -5.0, 5.0])
    overlap = bool(body and any(crosswalk[0] <= v[0] <= crosswalk[1] and
                                crosswalk[2] <= v[1] <= crosswalk[3] for v in body))
    gap = None
    if other and body and other.get('body_vertices_m'):
        lead_back = min(v[0] for v in other['body_vertices_m'])
        subject_front = max(v[0] for v in body)
        gap = max(0.0, lead_back - subject_front)
    scenario = point.get('scenario_measurements', {})
    widths = {'ego_width_m': max(v[1] for v in body) - min(v[1] for v in body) if body else None,
              'other_width_m': max(v[1] for v in other['body_vertices_m']) -
                  min(v[1] for v in other['body_vertices_m']) if other and other.get('body_vertices_m') else None}
    return {
        'kin.position': point['position_m'],
        'kin.heading': point['heading_deg'],
        'kin.speed': point['speed_mps'],
        'native_context': {'frame': frame, 'map_context': obs.get('map_context'),
                           'world_settings': obs.get('world_settings'),
                           'native_actor_inventory': obs.get('participants', []),
                           'native_sign_inventory': scenario.get('native_sign_inventory'),
                           'officer_control': 'unconfirmed; synthetic authored absence only',
                           'road_projection': event['world']['road_projection']},
        'road_geometry': {'frame': frame, 'projection': event['world']['road_projection'],
                          'native_map_facts_reference': 'capture/native_map_facts.json',
                          'authored_regions': config.get('authored_regions', {}),
                          'signed_entrances': config.get('signed_entrances', []),
                          'native_sign_inventory': scenario.get('native_sign_inventory')},
        'motion_event': {'frame': frame, 'route_index': route_index,
                         'position_m': point['position_m'], 'heading_deg': point['heading_deg'],
                         'speed_mps': point['speed_mps'],
                         'reverse_control': bool(point['control']['reverse']),
                         'stationary': point['speed_mps'] < .1},
        'participant_relation': {'frame': frame, 'other': other,
                                 'subject_body_vertices_m': body,
                                 'measured_widths': widths,
                                 'legal_priority': 'unresolved',
                                 'immediate_hazard': 'unresolved'},
        'visibility_rays': {'frame': frame, 'same_frame': scenario.get('bidirectional_sight'),
                            'subject_rays': event.get('visibility'),
                            'sampled_visible_range_m': scenario.get('sampled_visible_range_m')},
        'surface_gap': {'frame': frame, 'gap_m': gap, 'measured_widths': widths,
                        'basis': 'full original body vertices projected longitudinally'},
        'crosswalk_overlap': {'frame': frame, 'body_overlap': overlap,
                              'reverse_control': bool(point['control']['reverse']),
                              'crosswalk_box_m': crosswalk,
                              'boundary_kind': 'authored diagnostic; native marking/geometry requires inspection'},
    }


def run(args):
    import carla  # lazy: CPU checks never connect
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    config = read(ROOT / 'config.json')
    case = config['case']
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'trace.jsonl').exists() or (output / 'video_frames.jsonl').exists():
        raise ValueError('Original evidence exists; choose a fresh attempt')
    if not (output / 'config.json').exists():
        (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(args.host, args.port)
    client.set_timeout(120)
    saved = snapshot(client)
    owned, encoders, cameras, channels = [], [], [], {}
    capture = None
    capture_complete = False
    try:
        world = client.generate_opendrive_world((ROOT / 'scene.xodr').read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        native_signs = []
        for landmark in mapping.get_all_landmarks():
            native_signs.append({'id': str(landmark.id), 'type': str(landmark.type),
                                 'road_id': landmark.road_id, 's_m': landmark.s,
                                 'orientation': str(landmark.orientation)})
        (output / 'native-signs.json').write_text(json.dumps({'source': 'Map.get_all_landmarks',
            'complete_inventory': True, 'landmarks': native_signs}, indent=2) + '\n')
        (output / 'native-topology.json').write_text(json.dumps({'edges': [
            {'from': [a.road_id, a.lane_id], 'to': [b.road_id, b.lane_id]}
            for a, b in mapping.get_topology()]}, indent=2) + '\n')
        ego_points = route(config, case)
        blueprint = world.get_blueprint_library().find(config['ego_blueprint'])
        blueprint.set_attribute('role_name', 'ego')
        reverse = config['mode'] == 'reverse_crosswalk'
        initial_yaw = 165.0 / CURVE_RADIUS_M * 180.0 / math.pi if config['mode'] == 'curve_u_turn' else 0.0
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=ego_points[0][0], y=ego_points[0][1], z=.5),
            carla.Rotation(yaw=initial_yaw)))
        owned.append(ego)
        participant = None
        participant_points = []
        if config['mode'] in ('signed_yield', 'signed_non_through', 'truck_follow'):
            participant_points = route(config, case, 'other')
            other_bp = world.get_blueprint_library().find(config['other_blueprint'])
            other_bp.set_attribute('role_name', 'other')
            participant = world.spawn_actor(other_bp, carla.Transform(
                carla.Location(x=participant_points[0][0], y=participant_points[0][1], z=.5),
                carla.Rotation(yaw=90 if config['mode'].startswith('signed') else 0)))
            owned.append(participant)
        for i, spec in enumerate(config['cameras']):
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in [('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('sensor_tick', '0')]:
                bp.set_attribute(key, str(value))
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
            cameras.append((sensor, frames))
            encoders.append((proc, log))
        for _ in range(5):
            world.tick()
        capture = PipelineCapture(client, ego, output, case['case_id'],
                                  visibility=config['mode'] in ('signed_yield', 'signed_non_through',
                                                                 'curve_u_turn'),
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
                command, index = control(carla, ego, ego_points, config['target_speed_mps'], reverse)
                if config['mode'].startswith('signed') and ego.get_transform().location.x < -6.0:
                    wait_s = case['variable_assignments']['requested_wait_s']['value']
                    if wait_s > 0 and world.get_snapshot().timestamp.elapsed_seconds - start < wait_s:
                        command = carla.VehicleControl(brake=1.0)
                ego.apply_control(command)
                if participant is not None:
                    other_control, _ = control(carla, participant, participant_points,
                                               config['other_speed_mps'])
                    participant.apply_control(other_control)
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - start
                sight = None
                if config['mode'] == 'curve_u_turn':
                    # Place both observers on native opposite-direction lanes
                    # at exact arc-length stations around the turn. Only samples
                    # near the turn station represent this legal probe.
                    eye = ego.get_transform().location
                    details = []
                    probe = case['variable_assignments']['sight_probe_m']['value']
                    native_ego = mapping.get_waypoint(eye, project_to_road=True)
                    at_turn = native_ego is not None and abs(native_ego.s - TURN_STATION_M) <= 5
                    for direction, station, lane_id in zip((-1, 1), sight_stations(probe), (-1, 1)):
                        observer = mapping.get_waypoint_xodr(1, lane_id, station)
                        if observer is None:
                            raise RuntimeError('Native map lacks requested sight observer station')
                        location = observer.transform.location
                        start_ray = carla.Location(x=location.x, y=location.y, z=location.z + 1.5)
                        finish_ray = carla.Location(x=eye.x, y=eye.y, z=eye.z + 1.5)
                        hits = world.cast_ray(start_ray, finish_ray) if at_turn else []
                        details.append({'direction': direction, 'road_id': observer.road_id,
                                        'lane_id': observer.lane_id, 'road_station_m': observer.s,
                                        'ego_road_station_m': native_ego.s if native_ego is not None else None,
                                        'observer_m': [start_ray.x, start_ray.y, start_ray.z],
                                        'target_m': [finish_ray.x, finish_ray.y, finish_ray.z],
                                        'hit_count': len(hits) if at_turn else None,
                                        'probe_distance_m': probe, 'at_turn_station': at_turn,
                                        'visible_at_probe': len(hits) == 0 if at_turn else None})
                    sight = details
                elif config['mode'] in ('signed_yield', 'signed_non_through') and participant is not None:
                    eye = ego.get_transform().location
                    target = participant.get_transform().location
                    start_ray = carla.Location(x=eye.x, y=eye.y, z=eye.z + 1.4)
                    finish_ray = carla.Location(x=target.x, y=target.y, z=target.z + 1.0)
                    hits = world.cast_ray(start_ray, finish_ray)
                    sight = [{'observer_m': [start_ray.x, start_ray.y, start_ray.z],
                              'target_m': [finish_ray.x, finish_ray.y, finish_ray.z],
                              'hit_count': len(hits), 'target_visible_by_ray': len(hits) == 0,
                              'purpose': 'engineering geometric ray only; actual driver view unresolved'}]
                extra = {'scenario_measurements': {'bidirectional_sight': sight,
                    'sampled_visible_range_m': (probe if all(v['visible_at_probe'] for v in sight) else 0.0)
                        if config['mode'] == 'curve_u_turn' and sight and sight[0]['at_turn_station'] else None,
                    'native_sign_inventory': native_signs}}
                point = capture.capture(frame, now, extra=extra)
                event = json.loads(evidence.readline())
                if event['original_frame'] != frame:
                    raise RuntimeError('Original capture/evidence frame mismatch')
                pose = ego.get_transform()
                body = [[v.x, v.y, v.z] for v in ego.bounding_box.get_world_vertices(pose)]
                other = None
                if participant is not None:
                    other_pose = participant.get_transform()
                    other = {'actor_id': participant.id,
                        'blueprint': participant.type_id,
                        'position_m': [other_pose.location.x, other_pose.location.y, other_pose.location.z],
                        'speed_mps': participant.get_velocity().length(),
                        'body_vertices_m': [[v.x, v.y, v.z] for v in participant.bounding_box.get_world_vertices(other_pose)]}
                values = source_values(config, point, event, index, body, other, frame)
                samples.write(json.dumps({'frame': frame, 'time_s': now, 'route_index': index,
                    'ego_body_vertices_m': body, 'other': other, 'source_values': values}) + '\n')
                for name, stream in channels.items():
                    stream.write(json.dumps({'time_s': now, 'value': values[name]}) + '\n')
                source_frames = {}
                for i, (_, frames) in enumerate(cameras):
                    image = frames.get(timeout=45)
                    while image.frame < frame:
                        image = frames.get(timeout=45)
                    if image.frame != frame:
                        raise RuntimeError('Camera/source frame differs')
                    raw = bytes(image.raw_data)
                    encoders[i][0].stdin.write(raw)
                    source_frames['view%d' % i] = {'width': image.width, 'height': image.height,
                        'source_bgra_sha256': hashlib.sha256(raw).hexdigest()}
                frame_map.append(frame, now, source_frames=source_frames)
                if index >= len(ego_points)-1 and point['speed_mps'] < 2:
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
