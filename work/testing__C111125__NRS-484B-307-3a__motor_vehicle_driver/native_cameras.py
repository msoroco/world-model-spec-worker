"""Four original RGB views joined to each Native world frame.

Camera placement is read from the source-sealed site. The caller owns the world
and closes this capture before destroying the ego actor.
"""
from __future__ import annotations

import io
import queue
import subprocess
from pathlib import Path

from PIL import Image

from dual_green import require


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {name: ((1920, 1080) if name == "overview" else (1280, 720))
              for name in CAMERAS}


class CameraCapture:
    def __init__(self, world, ego, site, output, carla):
        self.output = Path(output)
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.closed = False
        self.overflow = False
        poses = site.get("camera_poses")
        require(isinstance(poses, dict) and set(poses) == set(CAMERAS),
                "source-surveyed four-camera poses missing")
        try:
            for name in CAMERAS:
                pose = poses[name]
                require(set(pose) == {"position_xyz", "rotation_ypr_deg", "attach_to_ego"},
                        "camera pose survey malformed")
                require(pose["attach_to_ego"] is (name == "driver_reference"),
                        "driver-reference camera attachment mismatch")
                position = pose["position_xyz"]
                orientation = pose["rotation_ypr_deg"]
                require(len(position) == 3 and len(orientation) == 3,
                        "camera pose dimensions invalid")
                transform = carla.Transform(
                    carla.Location(x=float(position[0]), y=float(position[1]), z=float(position[2])),
                    carla.Rotation(yaw=float(orientation[0]), pitch=float(orientation[1]),
                                   roll=float(orientation[2])))
                width, height = DIMENSIONS[name]
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                require(blueprint is not None, "Native RGB camera blueprint missing")
                for key, value in (("image_size_x", width), ("image_size_y", height),
                                   ("sensor_tick", "0.05")):
                    blueprint.set_attribute(key, str(value))
                sensor = world.spawn_actor(blueprint, transform, attach_to=ego) if pose[
                    "attach_to_ego"] else world.spawn_actor(blueprint, transform)
                require(sensor is not None, "Native camera spawn failed: " + name)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=8)
                self.queues[name] = frames
                def receive(image, inbox=frames):
                    try:
                        inbox.put_nowait(image)
                    except queue.Full:
                        self.overflow = True
                sensor.listen(receive)
                encoder = subprocess.Popen([
                    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                    "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                    f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                    "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                    str(self.output / (name + ".mkv")),
                ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                self.encoders[name] = encoder
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        require(not self.closed and not self.overflow, "Native camera acquisition unavailable")
        pngs = {}
        for name in CAMERAS:
            image = self.queues[name].get(timeout=15)
            while image.frame < frame:
                image = self.queues[name].get(timeout=15)
            require(image.frame == frame, "camera/world frame mismatch: " + name)
            width, height = DIMENSIONS[name]
            require(image.width == width and image.height == height,
                    "camera dimensions mismatch: " + name)
            raw = bytes(image.raw_data)
            require(len(raw) == width * height * 4, "camera BGRA payload incomplete")
            encoder = self.encoders[name]
            require(encoder.poll() is None and encoder.stdin is not None,
                    "camera encoder stopped early: " + name)
            encoder.stdin.write(raw)
            rgb = Image.frombytes("RGB", (width, height), raw, "raw", "BGRA")
            buffer = io.BytesIO()
            rgb.save(buffer, format="PNG")
            pngs[name] = buffer.getvalue()
        return pngs

    def close(self):
        if self.closed:
            return
        self.closed = True
        for sensor in reversed(self.sensors):
            sensor.stop()
            sensor.destroy()
        failures = []
        for name, encoder in self.encoders.items():
            if encoder.stdin:
                encoder.stdin.close()
            if encoder.wait(timeout=30) != 0:
                failures.append(name)
        require(not failures, "camera encoder failed: " + ", ".join(failures))
