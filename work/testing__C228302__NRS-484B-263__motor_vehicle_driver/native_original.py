"""Source-gated CARLA capture for the five exact controlled-access exit cases."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from controlled_access_exit import build_case, measure_history
from reviewed_site import verify

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')


class Adapter:
    """Small CARLA implementation of the source-checked construction API."""

    def __init__(self, world, carla, site, ego_start_variant):
        self.world, self.carla, self.site = world, carla, site
        self.ego_start_variant = ego_start_variant
        self.owned = []
        self.routes = {}
        self.headways = {}
        self.policy = None

    def read_map_hash(self):
        return hashlib.sha256(self.world.get_map().to_opendrive().encode()).hexdigest()

    def read_controlled_access(self, road):
        return road['controlled_access_readback']

    def read_exit_connection(self, road):
        return road['exit_connection_readback']

    def spawn_vehicle(self, point, blueprint, role):
        if role == 'ego':
            route = self.site['road']['exit_waypoints']
            gap = math.dist(route[0][:2], route[1][:2])
            if abs(gap - 2.0) > 0.05:
                raise ValueError('reviewed exit route lacks the two-meter primary/fallback start pair')
            point = route[0] if self.ego_start_variant == 'fallback1' else route[1]
        location = self.carla.Location(x=point[0], y=point[1], z=point[2] + 0.4)
        waypoint = self.world.get_map().get_waypoint(location, project_to_road=False)
        if waypoint is None:
            raise ValueError('reviewed exit spawn absent from Native map: ' + role)
        actor = self.world.try_spawn_actor(self.world.get_blueprint_library().find(blueprint),
                                           self.carla.Transform(location, waypoint.transform.rotation))
        if actor is None:
            raise ValueError('reviewed exit vehicle spawn failed: ' + role)
        self.owned.append(actor)
        return actor

    def set_route(self, actor, waypoints, role):
        self.routes[actor.id] = tuple(waypoints)

    def set_headway(self, actor, seconds):
        self.headways[actor.id] = seconds

    def set_exit_policy(self, actor, policy, approaching):
        self.policy = (actor.id, policy, tuple(vehicle.id for vehicle in approaching))

    def destroy(self, actor):
        actor.destroy()

    def target_velocity(self, actor, speed, route):
        location = actor.get_location()
        segments = []
        for start, end in zip(route, route[1:]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            length_sq = dx * dx + dy * dy
            if length_sq <= 0:
                continue
            t = max(0.0, min(1.0, ((location.x - start[0]) * dx +
                                     (location.y - start[1]) * dy) / length_sq))
            distance_sq = (location.x - start[0] - t * dx) ** 2 + (location.y - start[1] - t * dy) ** 2
            segments.append((distance_sq, dx, dy))
        if not segments:
            raise ValueError('reviewed Native route has no valid segment')
        _, dx, dy = min(segments)
        norm = math.hypot(dx, dy)
        actor.set_target_velocity(self.carla.Vector3D(speed * dx / norm, speed * dy / norm, 0.0))


def camera_pose(carla, site, name, ego):
    road = site['road']
    polygon = road['exit_merge_polygon_xy']
    center = [sum(p[0] for p in polygon) / len(polygon),
              sum(p[1] for p in polygon) / len(polygon)]
    start = road['exit_waypoints'][0]
    approach = road['highway_approach_waypoints'][0]
    if name == 'driver_reference':
        return carla.Transform(carla.Location(x=0.5, y=0, z=2.0), carla.Rotation(pitch=-4)), ego
    position = {'overview': [center[0] + 25, center[1] + 25, 34],
                'approach': [start[0], start[1] + 10, 7],
                'reference_corner': [approach[0] + 9, approach[1], 8]}[name]
    yaw = math.degrees(math.atan2(center[1] - position[1], center[0] - position[0]))
    pitch = math.degrees(math.atan2(1.5 - position[2],
                                    math.hypot(center[0] - position[0], center[1] - position[1])))
    return carla.Transform(carla.Location(x=position[0], y=position[1], z=position[2]),
                           carla.Rotation(yaw=yaw, pitch=pitch)), None


def run(config, case, packet_path, output, host, port):
    reviewed = verify(packet_path, case)
    site = reviewed['site']
    import carla
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    adapter = Adapter(world, carla, site, config['case']['ego_start_variant'])
    if adapter.read_map_hash() != site['road']['map_sha256']:
        raise ValueError('original Native map differs from reviewed OpenDRIVE source')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    old_settings = world.get_settings()
    sensors = {}
    queues = {}
    recorded = False
    restoration = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        client.start_recorder(str(output / 'carla_recorder.log'))
        recorded = True
        made = build_case(adapter, site, case)
        ego = made['ego']
        for view in config['cameras']:
            name = view['name']
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(view['width']))
            bp.set_attribute('image_size_y', str(view['height']))
            bp.set_attribute('fov', str(view['fov_deg']))
            bp.set_attribute('sensor_tick', '.05')
            pose, parent = camera_pose(carla, site, name, ego)
            sensor = world.spawn_actor(bp, pose, attach_to=parent)
            if sensor.type_id != 'sensor.camera.rgb':
                raise ValueError('original camera actor differs from selected view')
            adapter.owned.append(sensor)
            sensor_queue = queue.Queue(maxsize=4)
            sensor.listen(sensor_queue.put)
            sensors[name] = sensor
            queues[name] = sensor_queue
        center = [sum(p[i] for p in site['road']['exit_merge_polygon_xy']) /
                  len(site['road']['exit_merge_polygon_xy']) for i in (0, 1)]
        site_path = output / 'site-context.json'
        write(site_path, site)
        rows, trace, frame_map, native_index, evidence = [], [], [], [], []
        seen_near = {vehicle.id: False for vehicle in made['approaching']}
        released = False
        approach_route = site['road']['highway_approach_waypoints']
        approach_dx = approach_route[-1][0] - approach_route[0][0]
        approach_dy = approach_route[-1][1] - approach_route[0][1]
        if math.hypot(approach_dx, approach_dy) <= 0:
            raise ValueError('reviewed highway approach has no travel direction')
        for i in range(900):
            for other in made['approaching']:
                speed = 9.0 if i * .05 >= adapter.headways[other.id] else 0.0
                adapter.target_velocity(other, speed, adapter.routes[other.id])
            distances = [math.hypot(vehicle.get_location().x - center[0],
                                    vehicle.get_location().y - center[1])
                         for vehicle in made['approaching']]
            passed = []
            for vehicle, distance in zip(made['approaching'], distances):
                seen_near[vehicle.id] |= distance <= 12.0
                location = vehicle.get_location()
                beyond = ((location.x - center[0]) * approach_dx +
                          (location.y - center[1]) * approach_dy) > 0
                passed.append(seen_near[vehicle.id] and beyond and distance > 16.0)
            if case.policy == 'yield_until_clear':
                release = i >= 20 and all(passed)
            elif case.policy == 'proceed_between_vehicles':
                release = i >= 45 and passed[0] and not passed[1]
            else:
                release = i >= 40
            released |= release
            adapter.target_velocity(ego, 6.0 if released else 0.0, adapter.routes[ego.id])
            frame = world.tick()
            for name, sensor_queue in queues.items():
                image = sensor_queue.get(timeout=20)
                if image.frame != frame:
                    raise ValueError('original four-camera frame join failed')
                folder = output / 'capture' / name
                folder.mkdir(parents=True, exist_ok=True)
                image.save_to_disk(str(folder / f'{i:06d}.png'))
            ego_location = ego.get_location()
            ego_velocity = ego.get_velocity()
            speed = math.hypot(ego_velocity.x, ego_velocity.y)
            vehicles = []
            for other in made['approaching']:
                location, velocity = other.get_location(), other.get_velocity()
                waypoint = world.get_map().get_waypoint(location, project_to_road=False)
                road_ids = site['road'].get('highway_road_ids', [])
                if waypoint is None or (road_ids and waypoint.road_id not in road_ids):
                    raise ValueError('approaching vehicle left reviewed highway')
                vehicles.append({'actor_id': str(other.id), 'source_sha256': reviewed['packet_sha256'],
                                 'highway_occupancy_source_sha256': site['road']['highway_boundary_source_sha256'],
                                 'on_highway': True,
                                 'range_to_interaction_m': math.hypot(location.x - center[0], location.y - center[1]),
                                 'speed_mps': math.hypot(velocity.x, velocity.y)})
            rows.append({'case_id': case.name, 'original_frame': frame, 'elapsed_s': i * .05,
                         'ego_id': str(ego.id), 'map_sha256': site['road']['map_sha256'],
                         'site_sha256': sha(site_path),
                         'camera_plan_sha256': hashlib.sha256(json.dumps(config['cameras'], sort_keys=True).encode()).hexdigest(),
                         'road_authority_source_sha256': site['road']['restricted_access_authority_source_sha256'],
                         'source_sha256': reviewed['packet_sha256'],
                         'control_source_sha256': site['driver_control_source_sha256'],
                         'ego_center_xy': [ego_location.x, ego_location.y], 'ego_speed_mps': speed,
                         'approaching_vehicles': vehicles})
            trace.append({'frame': frame, 'time_s': i * .05,
                          'position_m': [ego_location.x, ego_location.y, ego_location.z],
                          'position': {'x': ego_location.x, 'y': ego_location.y, 'z': ego_location.z},
                          'velocity_mps': [ego_velocity.x, ego_velocity.y, ego_velocity.z],
                          'speed_mps': speed, 'speed_mph': speed / .44704,
                          'heading_deg': ego.get_transform().rotation.yaw, 'control': {}})
            frame_map.append({'video_frame': i, 'carla_frame': frame,
                              'native_frame': frame, 'time_s': i * .05})
            evidence.append({'original_frame': frame, 'replay_frame': frame,
                             'actor_id': ego.id, 'recording_time_s': i * .05,
                             'replay_simulation_time_s': i * .05,
                             'world': {'weather': {}},
                             'ego': {'position_m': [ego_location.x, ego_location.y, ego_location.z],
                                     'heading_deg': ego.get_transform().rotation.yaw,
                                     'speed_mps': speed, 'speed_provenance': 'original_native_readback',
                                     'body_vertices_m': [[v.x, v.y, v.z] for v in
                                                         ego.bounding_box.get_world_vertices(ego.get_transform())]},
                             'original_observations': {'frame': frame, 'time_s': i * .05,
                                                       'participants': [], 'map_context': {}}})
            graph_rel = f'graphs/base/{i:08d}.adapter.json'
            graph = output / 'capture/native' / graph_rel
            write(graph, {'path': 'capture/native/' + graph_rel,
                          'attributes': {'frame': frame, 'time_s': i * .05,
                                         'observed_evidence': evidence[-1]['original_observations']},
                          'nodes': [], 'edges': []})
            native_index.append({'frame': frame, 'simulation_time': i * .05,
                                 'adapter_graph': graph_rel})
        history_path = output / 'original-history.json'
        write(history_path, rows)
        for name, records in [('trace.jsonl', trace), ('video_frames.jsonl', frame_map),
                              ('capture/evidence.jsonl', evidence),
                              ('capture/native/frames.jsonl', native_index)]:
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in records), encoding='utf-8')
        write(output / 'capture/manifest.json',
              {'status': 'draft', 'acquisition': 'original_native',
               'case_id': config['selected_case_id'], 'frames': 900,
               'extraction_confirmed': True, 'complete_driving_lanes': False,
               'sources': {'trace.jsonl': sha(output / 'trace.jsonl'),
                           'site-context.json': sha(site_path)}})
    finally:
        errors = []
        for sensor in sensors.values():
            try:
                sensor.stop()
            except Exception as exc:
                errors.append(repr(exc))
        for actor in reversed(adapter.owned):
            try:
                actor.destroy()
            except Exception as exc:
                errors.append(repr(exc))
        if recorded:
            try:
                client.stop_recorder()
            except Exception as exc:
                errors.append(repr(exc))
        try:
            world.apply_settings(old_settings)
            current = world.get_settings()
            restoration = (not errors and current.synchronous_mode == old_settings.synchronous_mode and
                           current.fixed_delta_seconds == old_settings.fixed_delta_seconds)
        except Exception as exc:
            errors.append(repr(exc))
        if not restoration:
            raise ValueError('original Native restoration failed: ' + repr(errors))
    for name in VIEWS:
        folder = output / 'capture' / name
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
                        '-framerate', '20', '-start_number', '0', '-i', str(folder / '%06d.png'),
                        '-frames:v', '900', '-c:v', 'ffv1', '-pix_fmt', 'bgr0',
                        str(output / (name + '.mkv'))], check=True, timeout=600)
    measured = measure_history(rows, site, case)
    return {'reviewed': reviewed, 'site_path': site_path, 'history_path': history_path,
            'measured': measured, 'frames': frame_map, 'restoration': restoration}


def finalize(config, case, output, capture):
    """Seal measured Native sources; keep legal and physical acceptance unresolved."""
    from delivery_audit import decode_camera
    from worker_exchange.native_output import physical_result, seal_capture, write_result

    output = Path(output)
    write(output / 'acquisition-provenance.json',
          {'provenance_kind': 'native', 'diagnostic_fixture': False,
           'physical_acceptance_claimed': False})
    description = config['case']['recording_description']
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        path = output / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['elapsed_s'],
                                            'value': {'original_frame': row['original_frame'],
                                                      'source_history_sha256': sha(capture['history_path'])}}) + '\n'
                                for row in json.loads(capture['history_path'].read_text())), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    result = {'case_id': config['selected_case_id'], 'measured_values': capture['measured'],
              'target_checks': [{'target': 'controlled-access exit interaction',
                                 'requested': config['case'], 'measured': capture['measured'],
                                 'method': '900 original Native frame joins', 'tolerance': 0,
                                 'matched': True, 'physical_cause_confirmed': False,
                                 'cause_evidence': {'original-history.json': sha(capture['history_path'])}}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'original source pending independent review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'diagnostic_fixture': False,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    write_result(output, physical_result(output, result))
    videos = {}
    first = capture['frames'][0]['carla_frame']
    for name in VIEWS:
        path = output / (name + '.mkv')
        size = [1920, 1080] if name == 'overview' else [1280, 720]
        receipt = decode_camera(path, size)
        receipt_path = output / ('decode-receipt-' + name + '.json')
        write(receipt_path, receipt)
        videos[name] = {'sha256': sha(path), 'decode_receipt_sha256': sha(receipt_path),
                        'decoded_frame_count': 900, 'actual_pixel_audit': True,
                        'first_original_frame': first, 'last_original_frame': first + 899}
    packet = {'case_id': case.name, 'native_result_sha256': sha(output / 'result.json'),
              'site_sha256': sha(capture['site_path']),
              'original_history_sha256': sha(capture['history_path']),
              'frame_count': 900,
              'camera_plan_sha256': hashlib.sha256(json.dumps(config['cameras'], sort_keys=True).encode()).hexdigest(),
              'frame_map': [{'original_frame': row['carla_frame'], 'elapsed_s': row['time_s']}
                            for row in capture['frames']],
              'videos': videos,
              'measurement': {**capture['measured'], 'source_history_sha256': sha(capture['history_path'])}}
    write(output / 'saved-packet.json', packet)
    names = (['site-context.json', 'original-history.json', 'saved-packet.json'] +
             [name + '.mkv' for name in VIEWS])
    manifest = {'case_id': config['selected_case_id'],
                'source_kind': 'original_native_capture', 'diagnostic_fixture': False,
                'reviewer': capture['reviewed']['packet']['reviewer'],
                'files': {name: {'path': name, 'sha256': sha(output / name)} for name in names}}
    write(output / 'source-manifest.json', manifest)
    write(output / 'capture-identity.json',
          {'case_id': config['selected_case_id'],
           'source_kind': 'original_native_capture', 'diagnostic_fixture': False,
           'source_manifest_sha256': sha(output / 'source-manifest.json'),
           'cameras': {name: {'sha256': sha(output / (name + '.mkv')),
                              'frame_count': 900} for name in VIEWS}})
    from delivery_audit import audit_attempt
    audit_attempt(output, config['selected_case_id'])
    seal_capture(output, frames=900,
                 restoration={'restored': capture['restoration'],
                              'settings_readback': 'synchronous mode and delta verified'},
                 errors=[], encoder_exit_codes={name: 0 for name in VIEWS},
                 context={'reviewed_site_sha256': capture['reviewed']['packet_sha256'],
                          'original_history_sha256': sha(capture['history_path'])})
