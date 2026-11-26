"""Lazy CARLA bridge for a source-surveyed controlled-access boundary and entry/exit route."""

import hashlib
import io
import math
from queue import Queue

from package_spec import CAMERA_NAMES


class CarlaAccessAdapter:
    native_attested = True

    def __init__(self, host, port, site, request, profile):
        import carla
        self.carla = carla
        self.client = carla.Client(str(host), int(port))
        self.client.set_timeout(20)
        self.world = self.client.get_world()
        self.settings = self.world.get_settings()
        self.site, self.request, self.profile = site, request, profile
        self.owned, self.queues = [], {}
        self.ego = None
        self.path_index = 0

    def configure(self):
        native_map = self.world.get_map()
        if native_map.name != self.site["map_name"] or hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() != self.site["map_sha256"]:
            raise ValueError("original Native OpenDRIVE source differs")
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def spawn(self):
        item = self.site["native_spawn"]
        pose = item["pose_xyz_ypr"]
        c = self.carla
        transform = c.Transform(c.Location(x=pose[0], y=pose[1], z=pose[2]),
                                c.Rotation(pitch=pose[3], yaw=pose[4], roll=pose[5]))
        ego = self.world.try_spawn_actor(self.world.get_blueprint_library().find(item["blueprint_id"]), transform)
        if ego is None or not ego.id or ego.get_transform() is None:
            raise ValueError("source-pose Native vehicle spawn failed")
        self.ego = ego
        self.owned.append(ego)
        offsets = {"overview": (-18, 0, 20), "approach": (-9, 3, 5),
                   "reference_corner": (3, 4, 5), "driver_reference": (0, 0, 2)}
        for index, name in enumerate(CAMERA_NAMES):
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            width, height = ((1920, 1080) if index == 0 else (1280, 720))
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", "0.05")
            xyz = offsets[name]
            sensor = self.world.spawn_actor(blueprint,
                c.Transform(c.Location(x=xyz[0], y=xyz[1], z=xyz[2])), attach_to=ego)
            queue = Queue()
            sensor.listen(queue.put)
            self.owned.append(sensor)
            self.queues[name] = queue

    def tick(self):
        loc = self.ego.get_location()
        path = self.request["trajectory_xy"]
        while self.path_index < len(path) - 1 and math.hypot(loc.x - path[self.path_index][0], loc.y - path[self.path_index][1]) < 4:
            self.path_index += 1
        target = path[self.path_index]
        desired_yaw = math.degrees(math.atan2(target[1] - loc.y, target[0] - loc.x))
        yaw = self.ego.get_transform().rotation.yaw
        delta = (desired_yaw - yaw + 180) % 360 - 180
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        gain = float(self.profile.get("steer_gain", .025))
        if not .015 <= gain <= .04:
            raise ValueError("controller steering gain out of bounds")
        self.ego.apply_control(self.carla.VehicleControl(
            throttle=max(0, min(.55, (8 - speed) * .18)),
            brake=max(0, min(.6, (speed - 8) * .2)),
            steer=max(-.7, min(.7, delta * gain))))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("Native frame identity differs")
        return frame, snapshot.timestamp.elapsed_seconds

    def read(self, frame, time_s):
        loc = self.ego.get_location()
        wp = self.world.get_map().get_waypoint(loc, project_to_road=False)
        if wp is None:
            raise ValueError("original Native lane/road waypoint absent")
        v = self.ego.get_velocity()
        speed = math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)
        maneuver = self.request["direction"]
        return {"frame": frame, "time_s": time_s, "original_frame": frame,
                "actor_ids": [str(self.ego.id)], "driver_id": self.site["driver_actor_id"],
                "lane_id": wp.lane_id, "road_id": wp.road_id,
                "junction_id": wp.get_junction().id if wp.is_junction else None,
                "maneuver": maneuver, "source_ref": self.site["reviewed_site_sha256"],
                "position_xyz_m": [loc.x, loc.y, loc.z],
                "heading_deg": self.ego.get_transform().rotation.yaw,
                "speed_mps": speed,
                "control": {"throttle": self.ego.get_control().throttle,
                            "brake": self.ego.get_control().brake,
                            "steer": self.ego.get_control().steer}}

    def pixels(self, frame):
        from PIL import Image
        images = {}
        for name in CAMERA_NAMES:
            image = self.queues[name].get(timeout=10)
            if image.frame != frame:
                raise ValueError("original camera frame differs: " + name)
            raw = Image.frombytes("RGBA", (image.width, image.height),
                                  bytes(image.raw_data), "raw", "BGRA")
            output = io.BytesIO()
            raw.convert("RGB").save(output, format="PNG")
            images[name] = {"frame": frame, "png": output.getvalue()}
        return images

    def cleanup(self):
        try:
            if self.ego is not None:
                self.ego.apply_control(self.carla.VehicleControl(brake=1))
        finally:
            for actor in reversed(self.owned):
                try:
                    actor.destroy()
                except Exception:
                    pass
            self.world.apply_settings(self.settings)
