"""Lazy CARLA bridge for reviewed right-side passing actors and cameras."""

import hashlib
import io
import math
from queue import Queue

from package_spec import CAMERA_NAMES
from right_pass import spawn_native


def need(ok, message):
    if not ok:
        raise ValueError(message)


class CarlaRightPassAdapter:
    native_attested = True

    def __init__(self, host, port, site, request, profile):
        import carla
        self.carla = carla
        self.client = carla.Client(str(host), int(port))
        self.client.set_timeout(20)
        self.world = self.client.get_world()
        self.settings = self.world.get_settings()
        self.site, self.request, self.profile = site, request, profile
        self.owned, self.actors, self.queues = [], {}, {}
        frame = site.get("road_frame")
        need(isinstance(frame, dict) and len(frame.get("origin_xy", ())) == 2 and
             len(frame.get("station_axis_xy", ())) == 2 and
             len(frame.get("left_axis_xy", ())) == 2 and frame.get("source_id"),
             "source-surveyed Native road frame missing")
        self.frame = frame

    def pose(self, values):
        c = self.carla
        return c.Transform(c.Location(x=values[0], y=values[1], z=values[2]),
                           c.Rotation(pitch=values[3], yaw=values[4], roll=values[5]))

    def configure(self):
        native_map = self.world.get_map()
        need(native_map.name == self.site["map_name"] and
             hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() ==
             self.site["map_sha256"], "original Native OpenDRIVE source differs")
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def spawn(self):
        spawned = spawn_native(self.world, self.world.get_blueprint_library(),
                               self.site, self.request, self.pose)
        self.actors = spawned
        self.owned.extend(self.actors.values())
        for role in ("ego", "target"):
            actor = self.actors[role]
            heading = actor.get_transform().rotation.yaw
            speed = self.request["ego_speed_mps" if role == "ego" else "target_speed_mps"]
            actor.set_target_velocity(self.carla.Vector3D(
                x=speed * math.cos(math.radians(heading)),
                y=speed * math.sin(math.radians(heading)), z=0))
        offsets = {"overview": (-15, 0, 22), "approach": (-10, 4, 6),
                   "reference_corner": (3, 5, 6), "driver_reference": (0, 0, 2)}
        for index, name in enumerate(CAMERA_NAMES):
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            width, height = ((1920, 1080) if index == 0 else (1280, 720))
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", "0.05")
            sensor = self.world.spawn_actor(blueprint,
                self.carla.Transform(self.carla.Location(*offsets[name])),
                attach_to=self.actors["ego"])
            queue = Queue()
            sensor.listen(queue.put)
            self.owned.append(sensor)
            self.queues[name] = queue

    def control(self):
        scale = float(self.profile.get("speed_scale", 1))
        need(.5 <= scale <= 1.2, "physical controller scale out of bounds")
        _, ego_y = self.body(self.actors["ego"])
        lateral_now = sum(ego_y) / 2
        lateral_error = self.request["ego_target_lateral_m"] - lateral_now
        lateral_gain = float(self.profile.get("lateral_gain", .055))
        need(.03 <= lateral_gain <= .09, "lateral controller gain out of bounds")
        for role in ("ego", "target"):
            actor = self.actors[role]
            velocity = actor.get_velocity()
            speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            target = self.request["ego_speed_mps" if role == "ego" else "target_speed_mps"] * scale
            actor.apply_control(self.carla.VehicleControl(
                throttle=max(0, min(.65, (target - speed) * .22)),
                brake=max(0, min(.65, (speed - target) * .24)),
                steer=max(-.45, min(.45, lateral_error * lateral_gain)) if role == "ego" else 0))

    def tick(self):
        self.control()
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        need(snapshot.frame == frame, "Native frame identity differs")
        return frame, snapshot.timestamp.elapsed_seconds

    def coordinates(self, vertex):
        x = vertex.x - self.frame["origin_xy"][0]
        y = vertex.y - self.frame["origin_xy"][1]
        station = x * self.frame["station_axis_xy"][0] + y * self.frame["station_axis_xy"][1]
        lateral = -(x * self.frame["left_axis_xy"][0] + y * self.frame["left_axis_xy"][1])
        return station, lateral

    def body(self, actor):
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        bottom = min(v.z for v in vertices)
        points = [self.coordinates(v) for v in vertices if abs(v.z - bottom) <= .01]
        need(len(points) == 4, "four original body corners missing")
        return ([min(v[0] for v in points), max(v[0] for v in points)],
                [min(v[1] for v in points), max(v[1] for v in points)])

    def read(self, frame, time_s):
        ego_s, ego_y = self.body(self.actors["ego"])
        target_s, target_y = self.body(self.actors["target"])
        speeds = {}
        for role in ("ego", "target"):
            v = self.actors[role].get_velocity()
            speeds[role] = math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)
        ego_station = sum(ego_s) / 2
        sections = self.site["cross_sections"]
        nearest = min(sections, key=lambda item: abs(item["station_m"] - ego_station))
        row = {"frame": frame, "time_s": time_s,
               "ego_body_s_bounds_m": ego_s, "ego_body_y_bounds_m": ego_y,
               "target_body_s_bounds_m": target_s, "target_body_y_bounds_m": target_y,
               "ego_speed_mps": speeds["ego"], "target_speed_mps": speeds["target"],
               "paved_y_bounds_m": nearest["paved_y_bounds_m"],
               "paved_section_source": nearest["source_ref"],
               "actor_ids": [str(self.actors[r].id) for r in self.actors],
               "ego_position_xyz_m": [self.actors["ego"].get_location().x,
                                      self.actors["ego"].get_location().y,
                                      self.actors["ego"].get_location().z],
               "ego_heading_deg": self.actors["ego"].get_transform().rotation.yaw,
               "ego_control": {"throttle": self.actors["ego"].get_control().throttle,
                               "brake": self.actors["ego"].get_control().brake,
                               "steer": self.actors["ego"].get_control().steer}}
        if "conflict" in self.actors:
            row["conflict_body_s_bounds_m"], row["conflict_body_y_bounds_m"] = \
                self.body(self.actors["conflict"])
        return row

    def pixels(self, frame):
        from PIL import Image
        images = {}
        for name in CAMERA_NAMES:
            image = self.queues[name].get(timeout=10)
            need(image.frame == frame, "original camera frame differs: " + name)
            raw = Image.frombytes("RGBA", (image.width, image.height),
                                  bytes(image.raw_data), "raw", "BGRA")
            output = io.BytesIO()
            raw.convert("RGB").save(output, format="PNG")
            images[name] = {"frame": frame, "png": output.getvalue()}
        return images

    def cleanup(self):
        try:
            for role in ("ego", "target"):
                if role in self.actors:
                    self.actors[role].apply_control(self.carla.VehicleControl(brake=1))
        finally:
            for actor in reversed(self.owned):
                try:
                    actor.destroy()
                except Exception:
                    pass
            self.world.apply_settings(self.settings)
            need(self.world.get_settings().synchronous_mode == self.settings.synchronous_mode,
                 "Native world restoration failed")
