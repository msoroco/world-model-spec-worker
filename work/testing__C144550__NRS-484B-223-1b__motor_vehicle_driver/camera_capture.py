"""Four original CARLA cameras joined to each 20 Hz Native world tick."""

from __future__ import annotations

import hashlib
import io
import json
import math
import queue
from pathlib import Path

from PIL import Image


SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


class FourCameras:
    def __init__(self, world, carla, packet, ego, *, sizes=None):
        self.sizes = SIZES if sizes is None else sizes
        if set(self.sizes) != set(SIZES):
            raise ValueError("four exact original views required")
        self.sensors = []
        self.queues = {}
        self.errors = []
        try:
            for name, (width, height) in self.sizes.items():
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                x, y, z, pitch, yaw = packet["camera_poses_xyz_pitch_yaw"][name]
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(pitch=pitch, yaw=yaw))
                sensor = world.spawn_actor(blueprint, transform,
                    attach_to=ego if name == "driver_reference" else None)
                if sensor is None:
                    raise ValueError("Native camera spawn failed: " + name)
                destination = queue.Queue(maxsize=4)
                self.sensors.append(sensor)
                self.queues[name] = destination
                def receive(image, stream=destination, label=name):
                    try:
                        stream.put_nowait(image)
                    except queue.Full:
                        self.errors.append("original camera queue overflow: " + label)
                sensor.listen(receive)
        except BaseException:
            self.close()
            raise

    def read(self, frame: int, elapsed: float):
        if self.errors:
            raise ValueError("; ".join(self.errors))
        views = {}
        for name, (width, height) in self.sizes.items():
            image = self.queues[name].get(timeout=15)
            if (image.frame != frame or image.width != width or image.height != height or
                    type(image.timestamp) not in (int, float) or
                    not math.isclose(image.timestamp, elapsed, rel_tol=0.0, abs_tol=.001)):
                raise ValueError("original camera frame/time/dimensions differ: " + name)
            if (not isinstance(image.raw_data, (bytes, bytearray, memoryview)) or
                    len(image.raw_data) != width * height * 4):
                raise ValueError("original camera BGRA pixels missing: " + name)
            rgb = Image.frombytes("RGBA", (width, height), bytes(image.raw_data), "raw", "BGRA").convert("RGB")
            data = io.BytesIO()
            rgb.save(data, format="PNG")
            views[name] = data.getvalue()
        return views

    def close(self):
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        self.sensors.clear()
        if errors:
            raise RuntimeError("original Native camera cleanup failed: " + "; ".join(errors))


class CameraStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.rows = []

    def append(self, index: int, frame: int, elapsed: float, views: dict):
        if index != len(self.rows) or set(views) != set(SIZES):
            raise ValueError("four-view original camera sequence differs")
        entry = {"frame": index, "native_frame": frame, "native_elapsed_s": elapsed,
                 "views": {}}
        for name, png in views.items():
            path = self.root / f"{name}-{index:06d}.png"
            if path.exists():
                raise ValueError("original camera PNG already exists")
            path.write_bytes(png)
            entry["views"][name] = {"path": path.name,
                "sha256": hashlib.sha256(png).hexdigest()}
        self.rows.append(entry)

    def close(self):
        if len(self.rows) != 900:
            raise ValueError("four-view original 900-frame capture incomplete")
        target = self.root / "camera-manifest.json"
        target.write_text(json.dumps(self.rows, indent=2, sort_keys=True) + "\n")
        return {"path": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
