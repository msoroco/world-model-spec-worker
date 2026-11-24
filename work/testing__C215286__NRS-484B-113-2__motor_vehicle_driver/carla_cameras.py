"""Four independently acquired original Native RGB views."""

import io
import queue

from site_packet import VIEWS


SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


class OriginalCameras:
    def __init__(self, world, carla, packet):
        self.sensors = {}
        self.queues = {}
        try:
            for name in VIEWS:
                station = packet["camera_transforms"][name]
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                if blueprint is None:
                    raise ValueError("Native RGB camera blueprint missing")
                width, height = SIZES[name]
                for attribute, value in (("image_size_x", width), ("image_size_y", height),
                                         ("sensor_tick", .05)):
                    blueprint.set_attribute(attribute, str(value))
                transform = carla.Transform(carla.Location(*station["xyz"]),
                                            carla.Rotation(*station["rpy"]))
                sensor = world.spawn_actor(blueprint, transform)
                if sensor is None:
                    raise ValueError("Native camera spawn failed: " + name)
                mailbox = queue.Queue(maxsize=3)
                sensor.listen(lambda image, box=mailbox: box.put_nowait(image))
                self.sensors[name] = sensor
                self.queues[name] = mailbox
        except BaseException:
            self.close()
            raise

    def read(self, native_frame):
        from PIL import Image

        observed = {}
        for name in VIEWS:
            try:
                source = self.queues[name].get(timeout=10)
            except queue.Empty as error:
                raise ValueError("original camera timed out: " + name) from error
            if source.frame != native_frame:
                raise ValueError("original camera frame differs: " + name)
            expected = SIZES[name]
            if (source.width, source.height) != expected:
                raise ValueError("original camera dimensions differ: " + name)
            rgba = Image.frombuffer("RGBA", expected, source.raw_data, "raw", "BGRA", 0, 1)
            buffer = io.BytesIO()
            rgba.convert("RGB").save(buffer, format="PNG")
            observed[name] = {"frame": source.frame,
                              "source_sensor": str(self.sensors[name].id),
                              "bytes": buffer.getvalue()}
        return observed

    def close(self):
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            finally:
                sensor.destroy()
