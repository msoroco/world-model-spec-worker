"""Lazy CARLA bridge for reviewed protected pavement and physical warnings."""

import hashlib
import math
from queue import Queue

from package_spec import CAMERA_NAMES


def need(value, message):
    if not value:
        raise ValueError(message)


class CarlaPavementAdapter:
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
        self.warnings = []
        self.route = []
        self.target_index = 1

    def location(self, xyz):
        return self.carla.Location(x=float(xyz[0]), y=float(xyz[1]),
                                   z=float(xyz[2]) if len(xyz) > 2 else 0.0)

    def configure(self, scene):
        native_map = self.world.get_map()
        need(native_map.name == self.site["map_name"], "Native map name differs")
        need(hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() ==
             self.site["map_sha256"], "Native map OpenDRIVE source differs")
        route = scene["vehicle_route_xy"]
        for xy in route:
            waypoint = native_map.get_waypoint(self.location(xy), project_to_road=False)
            need(waypoint is not None, "reviewed pavement route lacks Native waypoint")
        self.route = [self.location(xy) for xy in route]
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def mark_pavement(self, rectangle, condition):
        need(self.site.get("scene", {}).get("pavement_rect_m") == rectangle and
             self.site["scene"].get("pavement_condition") == condition,
             "reviewed Native pavement surface differs")
        need(self.site.get("pavement_surface_readback") == "reviewed_original_surface",
             "original pavement surface readback missing")

    def _spawn_prop(self, blueprint_id, xy):
        need(isinstance(blueprint_id, str) and blueprint_id.startswith("static.prop."),
             "reviewed physical warning prop blueprint required")
        actor = self.world.try_spawn_actor(
            self.world.get_blueprint_library().find(blueprint_id),
            self.carla.Transform(self.location(xy)))
        need(actor is not None and actor.type_id == blueprint_id,
             "physical warning prop spawn/readback failed")
        self.owned.append(actor)
        self.warnings.append(actor)
        return actor

    def place_barrier(self, rectangle, protection):
        blueprint = self.site.get("barrier_blueprint_id")
        centre = [(rectangle[0] + rectangle[2]) / 2,
                  (rectangle[1] + rectangle[3]) / 2,
                  self.site.get("warning_z_m", 0)]
        actor = self._spawn_prop(blueprint, centre)
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        bounds = [min(v.x for v in vertices), min(v.y for v in vertices),
                  max(v.x for v in vertices), max(v.y for v in vertices)]
        need(all(abs(a - b) <= .35 for a, b in zip(bounds, rectangle)),
             "spawned physical barrier differs from reviewed geometry")
        return actor

    def place_sign(self, xy, sign_text):
        identities = self.site.get("sign_blueprints", {})
        blueprint = identities.get(sign_text)
        need(blueprint and self.site.get("sign_text_readback", {}).get(blueprint) == sign_text,
             "reviewed physical warning sign text source missing")
        return self._spawn_prop(blueprint, xy)

    def spawn_warning_person(self, xy):
        blueprint = self.site.get("warning_person_blueprint_id")
        need(isinstance(blueprint, str) and blueprint.startswith("walker.pedestrian."),
             "reviewed warning person blueprint required")
        actor = self.world.try_spawn_actor(
            self.world.get_blueprint_library().find(blueprint),
            self.carla.Transform(self.location(xy)))
        need(actor is not None and actor.type_id == blueprint,
             "physical warning person spawn/readback failed")
        self.owned.append(actor)
        self.warnings.append(actor)
        return actor

    def spawn_vehicle(self, xy):
        blueprint = self.site.get("ego_blueprint_id")
        need(isinstance(blueprint, str) and blueprint.startswith("vehicle."),
             "reviewed motor vehicle blueprint required")
        start, target = self.route[:2]
        yaw = math.degrees(math.atan2(target.y - start.y, target.x - start.x))
        actor = self.world.try_spawn_actor(
            self.world.get_blueprint_library().find(blueprint),
            self.carla.Transform(self.location(xy), self.carla.Rotation(yaw=yaw)))
        need(actor is not None and actor.type_id == blueprint,
             "Native motor vehicle spawn/readback failed")
        self.owned.append(actor)
        self.ego = actor
        return actor

    def set_vehicle_route(self, vehicle, route):
        need(vehicle is self.ego and route == self.site["scene"]["vehicle_route_xy"],
             "reviewed vehicle route differs")
        offsets = {"overview": (-15, 0, 22), "approach": (-9, 4, 5),
                   "reference_corner": (4, 5, 7), "driver_reference": (0, 0, 2)}
        blueprints = self.world.get_blueprint_library()
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
        target_speed = 6 * scale
        self.ego.apply_control(self.carla.VehicleControl(
            throttle=max(0, min(.65, (target_speed - speed) * .18)),
            brake=max(0, min(.8, (speed - target_speed) * .25)),
            steer=max(-.65, min(.65, error / 40))))

    def tick(self):
        self.control()
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        need(snapshot.frame == frame, "Native snapshot frame differs")
        return frame, snapshot.timestamp.elapsed_seconds

    def read(self, frame, time_s, scene, case):
        transform = self.ego.get_transform()
        centre = transform.location
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        warning_ids = [str(item.id) for item in self.warnings]
        need(warning_ids, "spawned physical protection missing")
        return {"frame": frame, "time_s": time_s,
                "vehicle_id": str(self.ego.id),
                "vehicle_position_xy": [centre.x, centre.y],
                "ego_position_m": [centre.x, centre.y, centre.z],
                "heading_deg": transform.rotation.yaw, "speed_mps": speed,
                "protection": case.protection,
                "protection_present": all(item.is_alive for item in self.warnings),
                "employee_engaged": case.employee_engaged,
                "work_active": scene["work_active"],
                "employee_pavement_id": scene["employee_pavement_id"],
                "warning_actor_ids": warning_ids,
                "pavement_id": scene["pavement_id"],
                "reviewed_site_sha256": self.site["reviewed_site_sha256"]}

    def pixels(self, frame):
        import io
        from PIL import Image
        images = {}
        for name in CAMERA_NAMES:
            image = self.queues[name].get(timeout=10)
            need(image.frame == frame, "original camera frame differs: " + name)
            bgra = Image.frombytes("RGBA", (image.width, image.height),
                                   bytes(image.raw_data), "raw", "BGRA")
            stream = io.BytesIO()
            bgra.convert("RGB").save(stream, format="PNG")
            images[name] = {"frame": image.frame, "png": stream.getvalue()}
        return images

    def destroy(self, actor):
        if actor in self.owned:
            self.owned.remove(actor)
        actor.destroy()

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
