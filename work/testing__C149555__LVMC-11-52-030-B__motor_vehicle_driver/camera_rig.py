"""Four source-reviewed static CARLA cameras for the freight Native attempt."""

from __future__ import annotations

import io
import queue

from freight_contract import SourceError
from saved_delivery import CAMERAS


class CameraRig:
    def __init__(self, adapter, site: dict):
        self.adapter = adapter
        self.site = site
        self.queues = {name: queue.Queue(maxsize=8) for name in CAMERAS}
        self.sensors = []

    def __enter__(self):
        try:
            return self._start()
        except BaseException:
            self._close(raise_errors=False)
            raise

    def _start(self):
        carla = self.adapter.carla
        locations = self.site.get("camera_transforms")
        if not isinstance(locations, dict) or set(locations) != set(CAMERAS):
            raise SourceError("four source-reviewed camera transforms required")
        for name, (width, height) in CAMERAS.items():
            pose = locations[name]
            if not isinstance(pose, dict) or set(pose) != {"x", "y", "z", "pitch", "yaw", "roll"}:
                raise SourceError("incomplete source-reviewed camera pose: " + name)
            transform = carla.Transform(
                carla.Location(x=float(pose["x"]), y=float(pose["y"]), z=float(pose["z"])),
                carla.Rotation(pitch=float(pose["pitch"]), yaw=float(pose["yaw"]),
                               roll=float(pose["roll"])))
            blueprint = self.adapter._blueprint("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", self.site.get("camera_fov_deg", 75)),
                               ("sensor_tick", 0.05)):
                blueprint.set_attribute(key, str(value))
            sensor = self.adapter.world.try_spawn_actor(blueprint, transform)
            if sensor is None:
                raise SourceError("original camera spawn failed: " + name)
            self.adapter.owned.append(sensor)
            self.sensors.append(sensor)
            stream = self.queues[name]
            def receive(image, stream=stream, expected=(width, height)):
                if (image.width, image.height) != expected:
                    raise SourceError("original camera sensor size drift")
                from PIL import Image
                pixels = Image.frombytes("RGBA", expected, bytes(image.raw_data), "raw", "BGRA")
                output = io.BytesIO()
                pixels.convert("RGB").save(output, format="PNG")
                stream.put((image.frame, output.getvalue()), timeout=30)
            sensor.listen(receive)
        return self

    def read_camera(self, name: str, native_frame: int) -> tuple[int, bytes]:
        if name not in self.queues:
            raise SourceError("unknown original camera")
        try:
            frame, pixels = self.queues[name].get(timeout=30)
        except queue.Empty as error:
            raise SourceError("original camera timed out: " + name) from error
        if frame != native_frame:
            raise SourceError("original camera frame drift: " + name)
        return frame, pixels

    def __exit__(self, *_):
        self._close(raise_errors=True)

    def _close(self, *, raise_errors: bool):
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except Exception as error:
                errors.append(error)
            destroyed = False
            try:
                sensor.destroy()
                destroyed = True
            except Exception as error:
                errors.append(error)
            if destroyed and sensor in self.adapter.owned:
                self.adapter.owned.remove(sensor)
        self.sensors.clear()
        if errors and raise_errors:
            raise SourceError("original camera cleanup failed: " + str(errors[0]))
