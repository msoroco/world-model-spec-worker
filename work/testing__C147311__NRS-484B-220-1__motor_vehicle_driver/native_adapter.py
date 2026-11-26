"""Lazy CARLA adapter for reviewed one-way site; no synthetic source promotion."""
from __future__ import annotations

import hashlib
import json
import math
import queue
from pathlib import Path

from one_way_direction import construct, CASES


class NativeAdapter:
    def __init__(self, host: str, port: int, output_dir: Path, site_packet: Path):
        import carla
        self.carla = carla
        self.client = carla.Client(host, port)
        self.client.set_timeout(30.0)
        packet = json.loads(Path(site_packet).read_text(encoding='utf-8'))
        highway = packet['source_bindings']['highway']
        source = Path(site_packet).parent / highway['path']
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != highway['sha256'] or source.suffix.lower() != '.xodr':
            raise ValueError('reviewed OpenDRIVE highway source unavailable')
        self.world = self.client.generate_opendrive_world(data.decode('utf-8'))
        self.map_bytes = data
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.recorder_started = False
        self.restoration_verified = False
        self.owned = []
        self.sensors = {}
        self.old_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        try:
            self.world.apply_settings(settings)
            self.client.start_recorder(str(self.output_dir / 'carla_recorder.log'))
            self.recorder_started = True
        except Exception:
            self.world.apply_settings(self.old_settings)
            raise

    def place_one_way_sign(self, xy, direction):
        signs = self.world.get_blueprint_library().filter('static.prop.*oneway*')
        if not signs:
            raise ValueError('Native one-way sign asset absent; original sign governance requires local review')
        yaw = math.degrees(math.atan2(direction[1], direction[0]))
        transform = self.carla.Transform(self.carla.Location(x=xy[0], y=xy[1], z=0.0),
                                         self.carla.Rotation(yaw=yaw))
        sign = self.world.try_spawn_actor(signs[0], transform)
        if sign is None:
            raise ValueError('reviewed one-way sign spawn failed')
        self.owned.append(sign)
        return sign

    def spawn_vehicle(self, xy, lane):
        vehicles = self.world.get_blueprint_library().filter('vehicle.*')
        if not vehicles:
            raise ValueError('Native vehicle asset absent')
        waypoint = self.world.get_map().get_waypoint(self.carla.Location(x=xy[0], y=xy[1], z=0.0), project_to_road=False)
        if waypoint is None or abs(waypoint.lane_id) != lane:
            raise ValueError('reviewed one-way lane spawn absent in Native map')
        transform = waypoint.transform
        transform.location.z += 0.4
        ego = self.world.try_spawn_actor(vehicles[0], transform)
        if ego is None:
            raise ValueError('reviewed one-way vehicle spawn failed')
        self.owned.append(ego)
        return ego

    def set_route(self, ego, route, direction):
        self.route = route
        self.direction = direction
        self.ego = ego

    def execute(self, reviewed: dict, config: dict):
        scene = reviewed['scene']
        case = next(c for c in CASES if c.name == config['case']['variant'])
        construct(self, scene, case)
        route_start = scene['ego_route_xy'][0]
        route_end = scene['ego_route_xy'][-1]
        middle = [(route_start[i] + route_end[i]) / 2 for i in (0, 1)]
        sign_xy = scene['sign_xy']
        camera_sites = {
            'overview': ([middle[0], middle[1] + 24, 32], middle),
            'approach': ([route_start[0], route_start[1] + 9, 6], sign_xy),
            'reference_corner': ([sign_xy[0], sign_xy[1] + 7, 4], sign_xy),
        }
        for camera in config['cameras']:
            name = camera['name']
            bp = self.world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(camera['width']))
            bp.set_attribute('image_size_y', str(camera['height']))
            bp.set_attribute('fov', str(camera['fov_deg']))
            bp.set_attribute('sensor_tick', '0.05')
            if name == 'driver_reference':
                pose = self.carla.Transform(self.carla.Location(x=0.5, y=0, z=2.0),
                                            self.carla.Rotation(pitch=-4.0))
                parent = self.ego
            else:
                position, target = camera_sites[name]
                yaw = math.degrees(math.atan2(target[1] - position[1],
                                              target[0] - position[0]))
                pitch = math.degrees(math.atan2(1.0 - position[2],
                                                math.hypot(target[0] - position[0],
                                                           target[1] - position[1])))
                pose = self.carla.Transform(self.carla.Location(x=position[0], y=position[1], z=position[2]),
                                            self.carla.Rotation(pitch=pitch, yaw=yaw))
                parent = None
            sensor = self.world.spawn_actor(bp, pose, attach_to=parent)
            if sensor.type_id != 'sensor.camera.rgb':
                raise ValueError('original camera actor type differs from selected profile')
            self.owned.append(sensor)
            q = queue.Queue(maxsize=4)
            sensor.listen(q.put)
            self.sensors[name] = q
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / 'road.xodr').write_bytes(self.map_bytes)
        trace = (self.output_dir / 'trace.jsonl').open('x', encoding='utf-8')
        mapping = (self.output_dir / 'video_frames.jsonl').open('x', encoding='utf-8')
        evidence = (self.output_dir / 'capture/evidence.jsonl')
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence_stream = evidence.open('x', encoding='utf-8')
        native_index = self.output_dir / 'capture/native/frames.jsonl'
        native_index.parent.mkdir(parents=True, exist_ok=True)
        native_stream = native_index.open('x', encoding='utf-8')
        with (self.output_dir / 'native-frames.jsonl').open('x', encoding='utf-8') as stream:
            for i in range(900):
                direction = scene['designated_unit_xy']
                sign = 1 if case.direction == 'designated' else -1
                self.ego.set_target_velocity(self.carla.Vector3D(direction[0] * sign * 5.0,
                                                                 direction[1] * sign * 5.0, 0.0))
                frame = self.world.tick()
                for name, q in self.sensors.items():
                    image = q.get(timeout=20)
                    if image.frame != frame:
                        raise ValueError('original four-camera frame join failed')
                    folder = self.output_dir / 'capture' / name
                    folder.mkdir(parents=True, exist_ok=True)
                    image.save_to_disk(str(folder / f'{i:06d}.png'))
                position = self.ego.get_location()
                velocity = self.ego.get_velocity()
                transform = self.ego.get_transform()
                heading = transform.rotation.yaw
                speed = math.hypot(velocity.x, velocity.y)
                time_s = i / 20
                row = {'original_frame': frame, 'time_s': i / 20,
                       'ego_id': str(self.ego.id), 'position_xy': [position.x, position.y],
                       'velocity_xy': [velocity.x, velocity.y], 'lane': case.lane,
                       'sign_governs_route': True, 'site_sha256': reviewed['site_sha256'],
                       'source_hashes': reviewed['source_hashes']}
                for field in ('frame', 'ego_motion', 'ego_position'):
                    row[field + '_source_sha256'] = reviewed['site_sha256']
                for field in ('driver_control', 'lane_inventory', 'one_way_designation',
                              'sign_authority', 'sign_message', 'sign_orientation',
                              'sign_governance'):
                    row[field + '_source_sha256'] = reviewed['source_hashes'][field]
                stream.write(json.dumps(row) + '\n')
                trace.write(json.dumps({'frame': frame, 'time_s': time_s,
                                        'position_m': [position.x, position.y, position.z],
                                        'position': {'x': position.x, 'y': position.y, 'z': position.z},
                                        'speed_mps': speed, 'speed_mph': speed / .44704,
                                        'velocity_mps': [velocity.x, velocity.y, velocity.z],
                                        'heading_deg': heading, 'control': {}}) + '\n')
                mapping.write(json.dumps({'video_frame': i, 'carla_frame': frame,
                                          'native_frame': frame, 'time_s': time_s}) + '\n')
                bounds = self.ego.bounding_box.get_world_vertices(transform)
                observed = {'frame': frame, 'time_s': time_s, 'participants': [],
                            'map_context': {'declared_public_way_road_ids': []}}
                evidence_stream.write(json.dumps({'original_frame': frame,
                        'replay_frame': frame, 'actor_id': self.ego.id,
                        'recording_time_s': time_s, 'replay_simulation_time_s': time_s,
                        'world': {'weather': {}},
                        'ego': {'position_m': [position.x, position.y, position.z],
                                'heading_deg': heading, 'speed_mps': speed,
                                'speed_provenance': 'original_native_readback',
                                'body_vertices_m': [[v.x, v.y, v.z] for v in bounds]},
                        'original_observations': observed}) + '\n')
                graph_rel = f'graphs/base/{i:08d}.adapter.json'
                graph = self.output_dir / 'capture/native' / graph_rel
                graph.parent.mkdir(parents=True, exist_ok=True)
                graph.write_text(json.dumps({'path': 'capture/native/' + graph_rel,
                    'attributes': {'frame': frame, 'time_s': time_s,
                                   'observed_evidence': observed},
                    'nodes': [], 'edges': []}) + '\n', encoding='utf-8')
                native_stream.write(json.dumps({'frame': frame, 'simulation_time': time_s,
                                                'adapter_graph': graph_rel}) + '\n')
        for handle in (trace, mapping, evidence_stream, native_stream):
            handle.close()
        self.output_dir.joinpath('capture/manifest.json').write_text(json.dumps({
            'status': 'draft', 'acquisition': 'original_native',
            'case_id': config['selected_case_id'], 'frames': 900,
            'extraction_confirmed': True, 'complete_driving_lanes': False,
            'sources': {'road.xodr': hashlib.sha256(self.map_bytes).hexdigest(),
                        'trace.jsonl': hashlib.sha256((self.output_dir / 'trace.jsonl').read_bytes()).hexdigest()}
        }) + '\n', encoding='utf-8')

    def destroy(self, actor):
        actor.destroy()

    def close(self):
        errors = []
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                if actor.destroy() is False:
                    errors.append('Native actor destruction returned false')
            except Exception as error:
                errors.append(repr(error))
        if self.recorder_started:
            try:
                self.client.stop_recorder()
                self.recorder_started = False
                details = self.client.show_recorder_file_info(
                    str(self.output_dir / 'carla_recorder.log'), False)
                (self.output_dir / 'capture/recorder_info.txt').write_text(
                    details, encoding='utf-8')
            except Exception as error:
                errors.append(repr(error))
        try:
            self.world.apply_settings(self.old_settings)
            restored = self.world.get_settings()
        except Exception as error:
            errors.append(repr(error))
            restored = None
        self.restoration_verified = (
            not errors and
            restored is not None and
            restored.synchronous_mode == self.old_settings.synchronous_mode and
            restored.fixed_delta_seconds == self.old_settings.fixed_delta_seconds)
        if not self.restoration_verified:
            raise ValueError('original Native actor/settings restoration not verified: ' + repr(errors))
