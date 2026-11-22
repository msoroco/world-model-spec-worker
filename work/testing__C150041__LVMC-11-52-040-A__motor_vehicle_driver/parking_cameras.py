"""Four synchronized original camera sources for a standing/parking attempt.

CARLA objects and FFmpeg processes are supplied only when a Native attempt runs.
"""
from __future__ import annotations

import math
import queue
import subprocess
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
RATE_HZ = 20
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def camera_poses(scene):
    target = scene["target_pose"]["target_center_xy_m"]
    spawn = scene["spawn_center_xy_m"]
    forward = scene["target_pose"]["target_forward_xy"]
    approach_yaw = math.degrees(math.atan2(target[1] - spawn[1], target[0] - spawn[0]))
    corner = [target[0] - 4 * forward[1], target[1] + 4 * forward[0]]
    corner_yaw = math.degrees(math.atan2(target[1] - corner[1], target[0] - corner[0]))
    return {
        "overview": {"xyz": [target[0], target[1], 18], "yaw": approach_yaw,
                     "pitch": -90, "attached": False},
        "approach": {"xyz": [spawn[0], spawn[1], 5], "yaw": approach_yaw,
                     "pitch": -25, "attached": False},
        "reference_corner": {"xyz": [*corner, 5], "yaw": corner_yaw,
                             "pitch": -40, "attached": False},
        "driver_reference": {"xyz": [0.5, 0, 1.4], "yaw": 0,
                             "pitch": 0, "attached": True},
    }


class CameraCapture:
    def __init__(self, world, vehicle, scene, output, carla, *, popen=None):
        self.sensors = []
        self.processes = {}
        self.queues = {}
        self.closed = False
        popen = popen or subprocess.Popen
        try:
            for name, (width, height) in zip(CAMERAS, SIZES):
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                if blueprint is None:
                    raise ValueError("original RGB camera blueprint missing")
                for key, value in (("image_size_x", width), ("image_size_y", height),
                                   ("fov", 90)):
                    blueprint.set_attribute(key, str(value))
                pose = camera_poses(scene)[name]
                x, y, z = pose["xyz"]
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(yaw=pose["yaw"],
                                                           pitch=pose["pitch"]))
                sensor = (world.spawn_actor(blueprint, transform, attach_to=vehicle)
                          if pose["attached"] else world.spawn_actor(blueprint, transform))
                if sensor is None:
                    raise RuntimeError("original camera spawn failed: " + name)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=8)
                self.queues[name] = frames
                sensor.listen(lambda image, q=frames: q.put_nowait(image))
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                           "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                           f"{width}x{height}", "-framerate", str(RATE_HZ), "-i", "pipe:0",
                           "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                           str(Path(output) / (name + ".mkv"))]
                self.processes[name] = popen(command, stdin=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        for name in CAMERAS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("camera/world frame mismatch: " + name)
            self.processes[name].stdin.write(image.raw_data)

    def close(self):
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
                if process.wait(timeout=180) != 0:
                    errors.append("camera encoder failed: " + name)
            except BaseException as exc:
                errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
