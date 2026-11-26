"""Lazy CARLA bridge for source-reviewed highway and physical barrier motion."""

import hashlib
import math
from queue import Queue

from package_spec import CAMERA_NAMES


def need(value, message):
    if not value:
        raise ValueError(message)


class CarlaBarrierAdapter:
    native_attested = True

    def __init__(self, host, port, site, control_profile):
        import carla
        self.carla = carla
        self.client = carla.Client(str(host), int(port))
        self.client.set_timeout(20)
        self.world = self.client.get_world()
        self.site = site
        self.profile = control_profile
        self.original_settings = self.world.get_settings()
        self.owned = []
        self.cameras = {}
        self.queues = {}
        self.ego = None
        self.barrier = None
        self.route = []
        self.target_index = 1

    def location(self, xyz):
        return self.carla.Location(x=float(xyz[0]), y=float(xyz[1]),
                                   z=float(xyz[2]) if len(xyz) > 2 else 0.0)

    def configure(self, route):
        native_map = self.world.get_map()
        need(native_map.name == self.site["map_name"], "Native map name differs")
        need(hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() ==
             self.site["map_sha256"], "Native map OpenDRIVE source differs")
        waypoints = route["route_waypoints"]
        for xy in waypoints:
            waypoint = native_map.get_waypoint(self.location(xy), project_to_road=False)
            need(waypoint is not None and waypoint.is_junction is False,
                 "connected reviewed highway route lacks Native waypoint")
        self.route = [self.location(xy) for xy in waypoints]
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def spawn(self):
        blueprints = self.world.get_blueprint_library()
        barrier_blueprint = self.site.get("barrier_blueprint_id")
        need(isinstance(barrier_blueprint, str) and
             barrier_blueprint.startswith("static.prop."),
             "physical Native barrier blueprint required")
        rect = self.site["barrier_rectangle"]
        position = [(rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2,
                    self.site.get("barrier_z_m", 0)]
        self.barrier = self.world.try_spawn_actor(
            blueprints.find(barrier_blueprint),
            self.carla.Transform(self.location(position)))
        need(self.barrier is not None, "physical Native barrier spawn failed")
        self.owned.append(self.barrier)
        vertices = self.barrier.bounding_box.get_world_vertices(self.barrier.get_transform())
        bounds = [min(v.x for v in vertices), min(v.y for v in vertices),
                  max(v.x for v in vertices), max(v.y for v in vertices)]
        need(all(abs(a - b) <= .35 for a, b in zip(bounds, rect)),
             "spawned barrier footprint differs from source survey")
        blueprint_id = self.site.get("ego_blueprint_id")
        need(isinstance(blueprint_id, str) and blueprint_id.startswith("vehicle."),
             "motor vehicle blueprint required")
        spawn = self.route[0]
        yaw = math.degrees(math.atan2(self.route[1].y - spawn.y,
                                      self.route[1].x - spawn.x))
        self.ego = self.world.try_spawn_actor(
            blueprints.find(blueprint_id),
            self.carla.Transform(spawn, self.carla.Rotation(yaw=yaw)))
        need(self.ego is not None and self.ego.type_id == blueprint_id,
             "Native motor vehicle spawn/readback failed")
        self.owned.append(self.ego)
        offsets = {"overview": (-15, 0, 22), "approach": (-9, 4, 5),
                   "reference_corner": (4, 5, 7), "driver_reference": (0, 0, 2)}
        for index, name in enumerate(CAMERA_NAMES):
            blueprint = blueprints.find("sensor.camera.rgb")
            width, height = ((1920, 1080) if index == 0 else (1280, 720))
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", "0.05")
            sensor = self.world.spawn_actor(blueprint, self.carla.Transform(
                self.carla.Location(*offsets[name])), attach_to=self.ego)
            queue = Queue()
            sensor.listen(queue.put)
            self.owned.append(sensor)
            self.cameras[name] = sensor
            self.queues[name] = queue

    def control(self):
        need(self.ego is not None, "Native ego absent")
        position = self.ego.get_location()
        while self.target_index + 1 < len(self.route) and \
                position.distance(self.route[self.target_index]) < 5:
            self.target_index += 1
        target = self.route[self.target_index]
        yaw = self.ego.get_transform().rotation.yaw
        desired = math.degrees(math.atan2(target.y - position.y,
                                          target.x - position.x))
        error = (desired - yaw + 180) % 360 - 180
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        scale = float(self.profile.get("speed_scale", 1))
        need(.4 <= scale <= 1.2, "engineering speed profile out of bounds")
        target_speed = 7 * scale
        control = self.carla.VehicleControl(
            throttle=max(0, min(.65, (target_speed - speed) * .18)),
            brake=max(0, min(.8, (speed - target_speed) * .25)),
            steer=max(-.65, min(.65, error / 40)))
        self.ego.apply_control(control)

    def tick(self):
        self.control()
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        need(snapshot.frame == frame, "Native snapshot frame differs")
        return frame, snapshot.timestamp.elapsed_seconds

    def read(self, frame, time_s):
        transform = self.ego.get_transform()
        vertices = self.ego.bounding_box.get_world_vertices(transform)
        bottom_z = min(vertex.z for vertex in vertices)
        footprint = [[vertex.x, vertex.y] for vertex in vertices
                     if abs(vertex.z - bottom_z) <= .01]
        need(len(footprint) == 4, "four original body footprint vertices missing")
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        rect = self.site["barrier_rectangle"]
        bounds = [min(v[0] for v in footprint), min(v[1] for v in footprint),
                  max(v[0] for v in footprint), max(v[1] for v in footprint)]
        overlap = (bounds[0] <= rect[2] and bounds[2] >= rect[0] and
                   bounds[1] <= rect[3] and bounds[3] >= rect[1])
        return {"frame": frame, "time_s": time_s,
                "ego_footprint_vertices": footprint, "speed_mps": speed,
                "barrier_contact": overlap, "ego_position_m":
                [transform.location.x, transform.location.y, transform.location.z],
                "heading_deg": transform.rotation.yaw,
                "ego_actor_id": str(self.ego.id),
                "barrier_actor_id": str(self.barrier.id),
                "ego_bounds_xy": bounds}

    def pixels(self, frame):
        import io
        images = {}
        for name in CAMERA_NAMES:
            image = self.queues[name].get(timeout=10)
            need(image.frame == frame, "original camera frame differs: " + name)
            from PIL import Image
            bgra = Image.frombytes("RGBA", (image.width, image.height),
                                   bytes(image.raw_data), "raw", "BGRA")
            stream = io.BytesIO()
            bgra.convert("RGB").save(stream, format="PNG")
            images[name] = {"frame": image.frame, "png": stream.getvalue()}
        return images

    def cleanup(self):
        try:
            if self.ego is not None:
                self.ego.apply_control(self.carla.VehicleControl(throttle=0, brake=1))
        finally:
            for actor in reversed(self.owned):
                try:
                    actor.destroy()
                except Exception:
                    pass
            self.world.apply_settings(self.original_settings)
            need(self.world.get_settings().synchronous_mode ==
                 self.original_settings.synchronous_mode,
                 "Native world setting restoration failed")
