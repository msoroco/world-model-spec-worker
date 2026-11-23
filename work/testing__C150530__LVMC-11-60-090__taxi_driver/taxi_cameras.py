"""Four original CARLA RGB views for the taxi stand and first right turn.

The constructor receives CARLA objects lazily. It preserves each full source
camera stream; composed video and pixel acceptance are later pipeline work.
"""
from __future__ import annotations

import math
import queue
import subprocess
from pathlib import Path

from stand_route import inspect as inspect_route

NAMES = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
RATE_HZ = 20


def poses(layout: dict) -> dict:
    inspect_route(layout)
    stand_x = layout["stand"]["center"][0]
    mid_x = (stand_x - 4.0) / 2
    corner_x, corner_y = -9.0, -10.0
    return {
        "overview": {"xyz": [mid_x, -2.0, 80.0], "yaw": 0.0,
                     "pitch": -90.0, "attached": False,
                     "subject": "stand-to-first-junction full route"},
        "approach": {"xyz": [stand_x - 7.0, -8.0, 5.0], "yaw": 10.0,
                     "pitch": -15.0, "attached": False,
                     "subject": "stand, posted notice and departing cab"},
        "reference_corner": {"xyz": [corner_x, corner_y, 7.0],
                             "yaw": math.degrees(math.atan2(-2.0 - corner_y,
                                                             -2.0 - corner_x)),
                             "pitch": -30.0, "attached": False,
                             "subject": "first junction and receiving south street"},
        "driver_reference": {"xyz": [0.5, 0.0, 1.4], "yaw": 0.0,
                             "pitch": 0.0, "attached": True,
                             "subject": "cab driver forward reference"},
    }


class CameraCapture:
    def __init__(self, world, vehicle, layout: dict, output: Path, carla, *, popen=None):
        self.sensors = []
        self.processes = {}
        self.queues = {}
        self.exit_codes = {}
        self.closed = False
        output = Path(output)
        popen = popen or subprocess.Popen
        try:
            for name, (width, height) in zip(NAMES, SIZES):
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                if blueprint is None:
                    raise ValueError("Native RGB camera blueprint missing")
                for key, value in (("image_size_x", width), ("image_size_y", height),
                                   ("fov", 90)):
                    blueprint.set_attribute(key, str(value))
                pose = poses(layout)[name]
                x, y, z = pose["xyz"]
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(yaw=pose["yaw"],
                                                           pitch=pose["pitch"]))
                sensor = (world.spawn_actor(blueprint, transform, attach_to=vehicle)
                          if pose["attached"] else world.spawn_actor(blueprint, transform))
                if sensor is None:
                    raise RuntimeError("Native camera spawn failed: " + name)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=8)
                self.queues[name] = frames
                sensor.listen(lambda image, q=frames: q.put_nowait(image))
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                           "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                           f"{width}x{height}", "-framerate", str(RATE_HZ), "-i", "pipe:0",
                           "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                           str(output / (name + ".mkv"))]
                self.processes[name] = popen(command, stdin=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame: int) -> None:
        if self.closed:
            raise ValueError("camera capture already closed")
        for name in NAMES:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("original camera/world frame mismatch: " + name)
            self.processes[name].stdin.write(image.raw_data)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as exc:
                errors.append(repr(exc))
        for name, process in self.processes.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                code = process.wait(timeout=180)
                self.exit_codes[name] = code
                if code != 0:
                    errors.append("original camera encoder failed: " + name)
            except BaseException as exc:
                errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
