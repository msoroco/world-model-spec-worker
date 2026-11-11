"""Four original-frame RGB sources for the fire-station reversal delivery attempt.

The caller owns the world and encoder sinks. Each sensor is attached to the
subject; a sink must retain its own unscaled source stream under the given name.
This module does not infer statutory caution or physical signal visibility from pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path
from threading import Condition
from time import monotonic


CAMERAS = {
    "overview": ((-10.0, 0.0, 8.0), (-12.0, 0.0, 0.0), (1920, 1080), 100),
    "approach": ((1.2, 0.0, 2.0), (0.0, 0.0, 0.0), (1280, 720), 90),
    "reference_corner": ((-5.0, 2.5, 3.5), (-8.0, 0.0, 0.0), (1280, 720), 100),
    "driver_reference": ((0.6, -0.35, 1.6), (0.0, 0.0, 0.0), (1280, 720), 85),
}


@dataclass(frozen=True)
class CameraPlan:
    name: str
    location: tuple[float, float, float]
    rotation: tuple[float, float, float]
    size: tuple[int, int]
    fov: int


def plans():
    return [CameraPlan(name, *spec) for name, spec in CAMERAS.items()]


class FFmpegSourceSink:
    """Retain one lossless, original-resolution BGRA stream from CARLA images."""

    def __init__(self, output, name, *, popen=subprocess.Popen):
        if name not in CAMERAS:
            raise ValueError("Unknown source camera")
        path = Path(output) / (name + ".mkv")
        if path.exists():
            raise ValueError("Retain prior source stream; use a fresh attempt")
        width, height = CAMERAS[name][2]
        self.size = width * height * 4
        self.process = popen(["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
                              "-f", "rawvideo", "-pixel_format", "bgra",
                              "-video_size", f"{width}x{height}", "-framerate", "20",
                              "-i", "pipe:0", "-an", "-c:v", "ffv1", str(path)],
                             stdin=subprocess.PIPE)
        self.closed = False

    def write(self, image):
        if self.closed:
            raise ValueError("Source stream already closed")
        raw = image.raw_data
        if len(raw) != self.size:
            raise ValueError("Source camera raw byte count changed")
        self.process.stdin.write(raw)

    def close(self):
        if not self.closed:
            self.closed = True
            self.process.stdin.close()
            if self.process.wait() != 0:
                raise ValueError("Source camera encoder failed")


class FireStationCameraCapture:
    def __init__(self, world, carla_module, subject, sinks):
        if set(sinks) != set(CAMERAS):
            raise ValueError("Exactly four named source-camera sinks are required")
        self.sensors = {}
        self.sinks = sinks
        self.frames = {name: set() for name in CAMERAS}
        self.condition = Condition()
        self.callback_errors = []
        self.closed = False
        library = world.get_blueprint_library()
        try:
            for plan in plans():
                bp = library.find("sensor.camera.rgb")
                for key, value in (("image_size_x", plan.size[0]),
                                   ("image_size_y", plan.size[1]),
                                   ("fov", plan.fov), ("sensor_tick", 0.05)):
                    bp.set_attribute(key, str(value))
                loc = carla_module.Location(*plan.location)
                pitch, yaw, roll = plan.rotation
                transform = carla_module.Transform(loc, carla_module.Rotation(pitch, yaw, roll))
                sensor = world.spawn_actor(bp, transform, attach_to=subject)
                self.sensors[plan.name] = sensor
                sensor.listen(lambda image, name=plan.name: self._on_frame(name, image))
        except BaseException:
            self.close()
            raise

    def _on_frame(self, name, image):
        with self.condition:
            if self.closed:
                return
            try:
                if image.frame in self.frames[name]:
                    raise ValueError("Duplicate original camera frame: " + name)
                expected = CAMERAS[name][2]
                if (image.width, image.height) != expected:
                    raise ValueError("Source camera dimensions changed: " + name)
                self.sinks[name].write(image)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.callback_errors.append(error)
                raise
            finally:
                self.condition.notify_all()

    def wait_for_frame(self, frame, timeout_s=10):
        """Join all original source pixels before writing that Native tick."""
        deadline = monotonic() + timeout_s
        with self.condition:
            while True:
                if self.callback_errors:
                    raise ValueError("Source camera callback failed") from self.callback_errors[0]
                if all(frame in rows for rows in self.frames.values()):
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    missing = sorted(name for name, rows in self.frames.items() if frame not in rows)
                    raise ValueError("Timed out waiting for source camera frame "
                                     + str(frame) + ": " + ", ".join(missing))
                self.condition.wait(remaining)

    def verify_frames(self, frames):
        if self.callback_errors:
            raise ValueError("Source camera callback failed") from self.callback_errors[0]
        expected = set(frames)
        if not expected:
            raise ValueError("No captured original frames")
        for name, observed in self.frames.items():
            if observed != expected:
                raise ValueError("Missing or extra source-camera frames: " + name)
        return {name: len(expected) for name in CAMERAS}

    def close(self):
        if not self.closed:
            self.closed = True
            for sensor in self.sensors.values():
                sensor.stop()
                sensor.destroy()
