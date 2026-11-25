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
        self.output_dir = Path(output_dir)
        self.owned = []
        self.sensors = {}
        self.old_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)

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
        for name in config['cameras']:
            bp = self.world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', '1920' if name == 'overview' else '1280')
            bp.set_attribute('image_size_y', '1080' if name == 'overview' else '720')
            bp.set_attribute('sensor_tick', '0.05')
            pose = self.carla.Transform(self.carla.Location(x=-7.0, y=0.0, z=3.0),
                                        self.carla.Rotation(pitch=-12.0))
            sensor = self.world.spawn_actor(bp, pose, attach_to=self.ego)
            self.owned.append(sensor)
            q = queue.Queue(maxsize=4)
            sensor.listen(q.put)
            self.sensors[name] = q
        self.output_dir.mkdir(parents=True, exist_ok=True)
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

    def destroy(self, actor):
        actor.destroy()

    def close(self):
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        self.world.apply_settings(self.old_settings)
