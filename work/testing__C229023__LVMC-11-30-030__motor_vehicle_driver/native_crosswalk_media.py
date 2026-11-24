"""Four same-tick original CARLA RGB streams for a reviewed crosswalk site.

The site packet supplies each camera's world pose and target. The caller must
bind that packet to its original map and owns the actor/world lifecycle.
"""

from __future__ import annotations

import math
import queue
import subprocess
import time
from pathlib import Path

from native_crosswalk_capture import CAMERAS, FRAME_COUNT
from saved_video_audit import DEFAULT_SIZES


def _xyz(value):
    if not isinstance(value, list) or len(value) != 3 or any(
        type(part) not in (int, float) or not math.isfinite(part) for part in value
    ):
        raise ValueError("finite original three-dimensional camera coordinates required")
    return value


class NativeCrosswalkCameras:
    def __init__(self, *, world, carla, site: dict, output: str | Path,
                 sizes: dict | None = None):
        self.sizes = dict(DEFAULT_SIZES if sizes is None else sizes)
        if set(self.sizes) != set(CAMERAS):
            raise ValueError("four exact camera views required")
        poses = site.get("camera_poses") if isinstance(site, dict) else None
        if not isinstance(poses, dict) or set(poses) != set(CAMERAS):
            raise ValueError("four reviewed original camera poses required")
        self.poses = {}
        for name in CAMERAS:
            row = poses[name]
            if not isinstance(row, dict):
                raise ValueError("original camera pose record required")
            self.poses[name] = (_xyz(row.get("location")), _xyz(row.get("target")))
        self.root = Path(output)
        if not self.root.is_dir() or any((self.root / (name + ".mkv")).exists() for name in CAMERAS):
            raise ValueError("fresh original video destination required")
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        self.frames = 0
        self.closed = False
        try:
            library = world.get_blueprint_library()
            for name in CAMERAS:
                width, height = self.sizes[name]
                if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
                    raise ValueError("positive exact camera dimensions required")
                bp = library.find("sensor.camera.rgb")
                if bp is None:
                    raise ValueError("Native RGB camera blueprint missing")
                for key, value in (("image_size_x", width), ("image_size_y", height), ("fov", 75)):
                    bp.set_attribute(key, str(value))
                location, target = self.poses[name]
                dx, dy, dz = [target[index] - location[index] for index in range(3)]
                if math.hypot(dx, dy) < 0.01:
                    raise ValueError("camera horizontal target direction required")
                yaw = math.degrees(math.atan2(dy, dx))
                pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
                transform = carla.Transform(carla.Location(x=location[0], y=location[1], z=location[2]),
                                            carla.Rotation(pitch=pitch, yaw=yaw))
                sensor = world.spawn_actor(bp, transform)
                if sensor is None:
                    raise RuntimeError("Native camera spawn failed: " + name)
                self.sensors.append(sensor)
                images = queue.Queue(maxsize=8)
                self.queues[name] = images
                def receive(image, *, view=name, target_queue=images):
                    try:
                        target_queue.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + view)
                sensor.listen(receive)
                process = subprocess.Popen([
                    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                    "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
                    "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1",
                    str(self.root / (name + ".mkv")),
                ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                self.encoders[name] = process
        except BaseException:
            self.close(require_complete=False)
            raise

    def append(self, world_frame: int):
        if self.closed or type(world_frame) is not int or world_frame < 0:
            raise ValueError("live original Native world frame required")
        if self.frames >= FRAME_COUNT:
            raise ValueError("camera capture exceeds planned duration")
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        images = {}
        for name in CAMERAS:
            deadline = time.monotonic() + 15
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("camera frame timeout: " + name)
                image = self.queues[name].get(timeout=remaining)
                if image.frame < world_frame:
                    continue
                if image.frame != world_frame:
                    raise RuntimeError("camera/world future-frame mismatch: " + name)
                expected = self.sizes[name][0] * self.sizes[name][1] * 4
                if len(image.raw_data) != expected:
                    raise ValueError("original BGRA image size differs: " + name)
                images[name] = image
                break
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        for name in CAMERAS:
            process = self.encoders[name]
            if process.poll() is not None:
                raise RuntimeError("camera encoder exited early: " + name)
            process.stdin.write(images[name].raw_data)
        self.frames += 1
        return images

    def close(self, *, require_complete: bool = True):
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as exc:
                errors.append(repr(exc))
        for name, process in self.encoders.items():
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
        if require_complete and self.frames != FRAME_COUNT:
            errors.append("incomplete 900-frame original camera capture")
        if errors:
            raise RuntimeError("; ".join(errors))
