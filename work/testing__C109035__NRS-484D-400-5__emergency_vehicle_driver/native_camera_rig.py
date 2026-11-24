"""Synchronized CARLA RGB sensor bridge for original emergency capture."""
from __future__ import annotations

from threading import Condition
import time

from camera_recorder import CAMERAS, PROFILE_SIZES
from native_handoff import validate_camera_plan


class NativeCameraRig:
    def __init__(self, world, ego, carla_api, site_packet: dict):
        plan = validate_camera_plan(site_packet)
        settings = world.get_settings()
        if (settings.synchronous_mode is not True or
                settings.no_rendering_mode is not False or
                abs(settings.fixed_delta_seconds - .05) > 1e-9):
            raise ValueError("Rendered synchronous 20 Hz world required")
        self.condition = Condition()
        self.pending = {}
        self.errors = []
        self.sensors = []
        blueprints = world.get_blueprint_library()
        try:
            for item in plan:
                blueprint = blueprints.find("sensor.camera.rgb")
                for key, value in (("image_size_x", item["width"]),
                                   ("image_size_y", item["height"]),
                                   ("fov", item["fov_deg"]), ("sensor_tick", "0.0")):
                    blueprint.set_attribute(key, str(value))
                location = item["location_xyz_m"]
                rotation = item["rotation_rpy_deg"]
                transform = carla_api.Transform(
                    carla_api.Location(x=location[0], y=location[1], z=location[2]),
                    carla_api.Rotation(roll=rotation[0], pitch=rotation[1],
                                       yaw=rotation[2]))
                kwargs = {"attach_to": ego} if item["attachment"] == "ego" else {}
                sensor = world.spawn_actor(blueprint, transform, **kwargs)
                if sensor is None:
                    raise ValueError("Original RGB camera spawn failed: " + item["name"])
                self.sensors.append(sensor)
                sensor.listen(lambda image, name=item["name"]: self._receive(name, image))
        except Exception:
            self.close()
            raise

    def _receive(self, name, image):
        try:
            width, height = PROFILE_SIZES[name]
            frame = image.frame
            if (type(frame) is not int or frame < 0 or image.width != width or
                    image.height != height or
                    len(image.raw_data) != width * height * 4):
                raise ValueError("Original camera frame or dimensions differ: " + name)
            with self.condition:
                key = name, frame
                if key in self.pending:
                    raise ValueError("Duplicate original camera frame: " + name)
                self.pending[key] = image
                self.condition.notify_all()
        except Exception as error:
            with self.condition:
                self.errors.append(error)
                self.condition.notify_all()

    def read(self, native_frame: int, timeout_s: float = 10.0):
        deadline = time.monotonic() + timeout_s
        with self.condition:
            while not self.errors and any((name, native_frame) not in self.pending
                                          for name in CAMERAS):
                left = deadline - time.monotonic()
                if left <= 0:
                    raise ValueError("Four original camera images missing")
                self.condition.wait(left)
            if self.errors:
                raise ValueError("Original camera callback failed: " + str(self.errors[0]))
            return {name: self.pending.pop((name, native_frame)) for name in CAMERAS}

    def close(self):
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception as error:
                errors.append(error)
        self.sensors.clear()
        if errors:
            raise ValueError("Original camera cleanup failed: " + str(errors[0]))
