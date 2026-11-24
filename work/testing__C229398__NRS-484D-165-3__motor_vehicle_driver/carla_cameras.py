"""Four original CARLA camera callbacks for source specified observation stations."""

from __future__ import annotations

import io
import queue

from parked_lamps import require

NAMES = ("front", "rear", "left", "right")


class OriginalCameras:
    def __init__(self, world, carla, site, config):
        transforms = site.get("camera_transforms")
        require(isinstance(transforms, dict) and set(transforms) == set(NAMES),
                "four sourced camera station transforms missing")
        self.sensors = {}
        self.queues = {}
        try:
            for entry in config["cameras"]:
                name = entry["name"]
                require(name in transforms and transforms[name].get("source"),
                        name + " camera station source missing")
                station = transforms[name]
                require(len(station.get("xyz", [])) == 3 and len(station.get("rpy", [])) == 3,
                        name + " camera station transform invalid")
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                require(blueprint is not None, "CARLA RGB camera blueprint missing")
                blueprint.set_attribute("image_size_x", str(entry["width"]))
                blueprint.set_attribute("image_size_y", str(entry["height"]))
                require(0 < entry["fov_deg"] < 180, name + " camera field of view invalid")
                blueprint.set_attribute("fov", str(entry["fov_deg"]))
                blueprint.set_attribute("sensor_tick", "0.05")
                transform = carla.Transform(carla.Location(*station["xyz"]), carla.Rotation(*station["rpy"]))
                sensor = world.spawn_actor(blueprint, transform)
                require(sensor is not None, name + " camera spawn failed")
                mailbox = queue.Queue(maxsize=3)
                sensor.listen(lambda image, box=mailbox: box.put_nowait(image))
                self.sensors[name] = sensor
                self.queues[name] = mailbox
        except Exception:
            self.close()
            raise

    def read(self, native_frame):
        from PIL import Image
        found = {}
        for name in NAMES:
            try:
                image = self.queues[name].get(timeout=10)
            except queue.Empty as error:
                raise ValueError(name + " original camera timed out") from error
            require(image.frame == native_frame, name + " camera frame does not match Native world")
            rgba = Image.frombuffer("RGBA", (image.width, image.height),
                                    image.raw_data, "raw", "BGRA", 0, 1)
            buffer = io.BytesIO()
            rgba.convert("RGB").save(buffer, format="PNG")
            found[name] = {"frame": image.frame, "source_sensor": str(self.sensors[name].id),
                           "bytes": buffer.getvalue()}
        return found

    def close(self):
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            finally:
                sensor.destroy()
