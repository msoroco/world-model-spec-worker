"""Lazy CARLA bridge for three source-identified bicycle riders."""
import hashlib
import io
import math
from queue import Queue
from abreast import SOURCES, construct
from package_spec import CAMERA_NAMES

def need(ok, message):
    if not ok:
        raise ValueError(message)

class CarlaRiderAdapter:
    native_attested = True

    def __init__(self, host, port, site, case, profile):
        import carla
        self.carla = carla
        self.client = carla.Client(str(host), int(port))
        self.client.set_timeout(20)
        self.world = self.client.get_world()
        self.settings = self.world.get_settings()
        self.site, self.scene, self.case, self.profile = site, site['scene'], case, profile
        self.owned, self.riders, self.routes, self.queues = [], {}, {}, {}

    def configure(self):
        native_map = self.world.get_map()
        need(native_map.name == self.site['map_name'] and hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() == self.site['map_sha256'], 'original Native map differs')
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def spawn_bicycle(self, rider_id, xy):
        c = self.carla
        blueprint = self.world.get_blueprint_library().find(self.site['bicycle_blueprint_id'])
        need(blueprint.id == self.site['bicycle_blueprint_id'], 'reviewed bicycle asset missing')
        actor = self.world.try_spawn_actor(blueprint, c.Transform(c.Location(x=xy[0], y=xy[1], z=self.site['spawn_z_m'])))
        need(actor is not None and actor.is_alive and actor.type_id == blueprint.id, 'Native bicycle spawn/readback failed')
        self.owned.append(actor)
        self.riders[rider_id] = actor
        return actor

    def set_route(self, actor, route):
        self.routes[str(actor.id)] = route

    def destroy(self, actor):
        actor.destroy()

    def spawn(self):
        built = construct(self, self.scene, self.case)
        need(len(built['owned']) == self.case.riders, 'rider group incomplete')
        offsets = {'overview': (-10, 0, 20), 'approach': (-6, 3, 5),
                   'reference_corner': (2, 5, 6), 'driver_reference': (0, 0, 2)}
        for i, name in enumerate(CAMERA_NAMES):
            bp = self.world.get_blueprint_library().find('sensor.camera.rgb')
            width, height = ((1920, 1080) if i == 0 else (1280, 720))
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('sensor_tick', '0.05')
            sensor = self.world.spawn_actor(bp, self.carla.Transform(self.carla.Location(*offsets[name])), attach_to=self.riders[self.scene['ego_id']])
            q = Queue()
            sensor.listen(q.put)
            self.owned.append(sensor)
            self.queues[name] = q

    def control(self):
        scale = float(self.profile.get('speed_scale', 1.0))
        need(.75 <= scale <= 1.1, 'rider engineering speed scale out of bounds')
        speed = float(self.site['engineering_speed_mps']) * scale
        need(0 < speed <= 4, 'rider speed source out of bounds')
        for rider_id in self.scene['rider_ids']:
            actor = self.riders[rider_id]
            route = self.routes[str(actor.id)]
            direction = [route[-1][i] - route[0][i] for i in range(2)]
            distance = math.hypot(*direction)
            need(distance >= 20, 'source route too short')
            actor.set_target_velocity(self.carla.Vector3D(x=speed * direction[0] / distance, y=speed * direction[1] / distance, z=0))

    def tick(self):
        self.control()
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        need(snapshot.frame == frame, 'Native frame identity differs')
        return frame, snapshot.timestamp.elapsed_seconds

    def read(self, frame, time_s):
        positions, speeds, actor_ids = [], [], []
        for rider_id in self.scene['rider_ids']:
            actor = self.riders[rider_id]
            point, velocity = actor.get_location(), actor.get_velocity()
            positions.append([point.x, point.y])
            speeds.append(math.hypot(velocity.x, velocity.y))
            actor_ids.append(str(actor.id))
        ego = self.riders[self.scene['ego_id']]
        pos = ego.get_location()
        return {'frame': frame, 'time_s': time_s, 'rider_ids': self.scene['rider_ids'],
                'native_actor_ids': actor_ids, 'exclusive': self.case.exclusive,
                'roadway': self.case.roadway, 'rider_xy': positions,
                'rider_speed_mps': speeds, 'ego_position_xyz_m': [pos.x, pos.y, pos.z],
                'ego_heading_deg': ego.get_transform().rotation.yaw,
                'ego_speed_mps': speeds[0], **{name + '_source_sha256': self.scene[name + '_source_sha256'] for name in SOURCES}}

    def pixels(self, frame):
        from PIL import Image
        images = {}
        for name in CAMERA_NAMES:
            image = self.queues[name].get(timeout=10)
            need(image.frame == frame, 'original rider camera frame differs: ' + name)
            raw = Image.frombytes('RGBA', (image.width, image.height), bytes(image.raw_data), 'raw', 'BGRA')
            output = io.BytesIO()
            raw.convert('RGB').save(output, format='PNG')
            images[name] = {'frame': frame, 'png': output.getvalue()}
        return images

    def cleanup(self):
        try:
            for rider in self.riders.values():
                rider.set_target_velocity(self.carla.Vector3D(x=0, y=0, z=0))
        finally:
            for actor in reversed(self.owned):
                try:
                    actor.destroy()
                except Exception:
                    pass
            self.world.apply_settings(self.settings)
            need(self.world.get_settings().synchronous_mode == self.settings.synchronous_mode, 'Native world restoration failed')
