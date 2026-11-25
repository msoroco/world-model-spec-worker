"""Four source-reviewed original CARLA RGB cameras for rider encounters."""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
from threading import Condition
import time

from PIL import Image


PROFILE = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _transform(carla, raw):
    if not isinstance(raw, dict) or set(raw) != {"x", "y", "z", "pitch", "yaw", "roll"}:
        raise ValueError("six reviewed camera transform coordinates required")
    values = {key: float(value) for key, value in raw.items()}
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("reviewed camera transform nonfinite")
    return carla.Transform(
        carla.Location(x=values["x"], y=values["y"], z=values["z"]),
        carla.Rotation(pitch=values["pitch"], yaw=values["yaw"],
                       roll=values["roll"]))


def _validate_transform(raw):
    if not isinstance(raw, dict) or set(raw) != {"x", "y", "z", "pitch", "yaw", "roll"}:
        raise ValueError("six reviewed camera transform coordinates required")
    if not all(math.isfinite(float(value)) for value in raw.values()):
        raise ValueError("reviewed camera transform nonfinite")


def load_review(path, expected_sha256, *, case_id, map_sha256):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("reviewed camera source missing")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("reviewed camera source hash drift")
    review = json.loads(path.read_text(encoding="utf-8"))
    if (review.get("format") != "c111260-reviewed-camera-plan-v1"
            or review.get("case_id") != case_id
            or review.get("map_sha256") != map_sha256
            or set(review.get("cameras", {})) != set(PROFILE)):
        raise ValueError("four exact source-reviewed cameras required")
    for name, spec in review["cameras"].items():
        if (spec.get("width"), spec.get("height")) != PROFILE[name]:
            raise ValueError("reviewed camera profile differs")
        if spec.get("attachment") not in ("world", "ego") or not 15 <= float(spec.get("fov_deg", 0)) <= 130:
            raise ValueError("reviewed camera attachment/FOV invalid")
        _validate_transform(spec.get("transform"))
    return review


class OriginalCameras:
    def __init__(self, world, carla, ego, review):
        self.world = world
        self.carla = carla
        self.ego = ego
        self.review = review
        self.sensors = {}
        self.pending = {name: {} for name in PROFILE}
        self.condition = Condition()

    def open(self):
        library = self.world.get_blueprint_library()
        try:
            for name, (width, height) in PROFILE.items():
                spec = self.review["cameras"][name]
                bp = library.find("sensor.camera.rgb")
                if bp is None or bp.id != "sensor.camera.rgb":
                    raise ValueError("original RGB camera blueprint unavailable")
                bp.set_attribute("image_size_x", str(width))
                bp.set_attribute("image_size_y", str(height))
                bp.set_attribute("sensor_tick", "0.05")
                bp.set_attribute("fov", str(spec["fov_deg"]))
                parent = self.ego if spec["attachment"] == "ego" else None
                sensor = self.world.spawn_actor(
                    bp, _transform(self.carla, spec["transform"]), attach_to=parent)
                if sensor is None:
                    raise ValueError("original camera spawn failed: " + name)
                self.sensors[name] = sensor
                sensor.listen(lambda image, view=name: self._on_image(view, image))
            if len({sensor.id for sensor in self.sensors.values()}) != 4:
                raise ValueError("four distinct original camera actors required")
            return self
        except Exception:
            self.close()
            raise

    def _on_image(self, name, image):
        width, height = PROFILE[name]
        if image.width != width or image.height != height or len(image.raw_data) != width * height * 4:
            return
        with self.condition:
            self.pending[name][int(image.frame)] = bytes(image.raw_data)
            self.condition.notify_all()

    def camera_png(self, name, frame, timeout_s=5.0):
        if name not in PROFILE:
            raise ValueError("unknown original camera")
        deadline = time.monotonic() + timeout_s
        with self.condition:
            while frame not in self.pending[name]:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("original camera frame missing: " + name)
                self.condition.wait(remaining)
            raw = self.pending[name].pop(frame)
        image = Image.frombytes("RGBA", PROFILE[name], raw, "raw", "BGRA").convert("RGB")
        target = io.BytesIO()
        image.save(target, format="PNG")
        return target.getvalue()

    def close(self):
        errors = []
        for sensor in self.sensors.values():
            for method in (sensor.stop, sensor.destroy):
                try:
                    method()
                except Exception as error:
                    errors.append(error)
        self.sensors.clear()
        if errors:
            raise RuntimeError("original camera cleanup failed") from errors[0]

    def __enter__(self):
        return self.open()

    def __exit__(self, *_):
        self.close()
