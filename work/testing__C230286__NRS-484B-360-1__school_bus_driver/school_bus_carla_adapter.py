"""Lazy CARLA bridge for source-reviewed school-bus route and four cameras."""

import hashlib
import io
import math
from queue import Queue

from package_spec import CAMERA_NAMES


class CarlaSchoolBusAdapter:
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
        self.bus = None

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
        bus = self.world.try_spawn_actor(self.world.get_blueprint_library().find(item["blueprint_id"]), transform)
        if bus is None or not bus.id or bus.get_transform() is None:
            raise ValueError("source-pose Native school bus spawn failed")
        self.bus = bus
        self.owned.append(bus)
        offsets = {"overview": (-25, 0, 22), "approach": (-12, 4, 6),
                   "reference_corner": (4, 5, 6), "driver_reference": (0, 0, 2)}
        for index, name in enumerate(CAMERA_NAMES):
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            width, height = ((1920, 1080) if index == 0 else (1280, 720))
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", "0.05")
            xyz = offsets[name]
            sensor = self.world.spawn_actor(blueprint,
                c.Transform(c.Location(x=xyz[0], y=xyz[1], z=xyz[2])), attach_to=bus)
            queue = Queue()
            sensor.listen(queue.put)
            self.owned.append(sensor)
            self.queues[name] = queue

    def tick(self):
        velocity = self.bus.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        target = self.request["target_speed_mps"]
        gain = float(self.profile.get("accel_gain", .22))
        if not .1 <= gain <= .35:
            raise ValueError("controller gain out of bounds")
        self.bus.apply_control(self.carla.VehicleControl(
            throttle=max(0, min(.65, (target - speed) * gain)),
            brake=max(0, min(.65, (speed - target) * .24)), steer=0))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("Native frame identity differs")
        return frame, snapshot.timestamp.elapsed_seconds

    def read(self, frame, time_s):
        v = self.bus.get_velocity()
        loc = self.bus.get_location()
        speed = math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)
        active = any(lo <= time_s < hi for lo, hi in self.request["transport_intervals_s"])
        return {"frame": frame, "time_s": time_s, "actor_ids": [str(self.bus.id)],
                "bus_speed_mps": speed, "bus_position_xyz_m": [loc.x, loc.y, loc.z],
                "bus_heading_deg": self.bus.get_transform().rotation.yaw,
                "transporting_pupils_to_or_from_school": active,
                "bus_control": {"throttle": self.bus.get_control().throttle,
                                "brake": self.bus.get_control().brake,
                                "steer": self.bus.get_control().steer}}

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
            if self.bus is not None:
                self.bus.apply_control(self.carla.VehicleControl(brake=1))
        finally:
            for actor in reversed(self.owned):
                try:
                    actor.destroy()
                except Exception:
                    pass
            self.world.apply_settings(self.settings)
