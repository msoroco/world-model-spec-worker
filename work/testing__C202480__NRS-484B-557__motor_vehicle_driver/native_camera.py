"""Source-bound four-view Native RGB acquisition with original frame joins."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from threading import Condition
import time


VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def _triplet(value, name):
    if (not isinstance(value, list) or len(value) != 3 or
            any(isinstance(n, bool) or not isinstance(n, (int, float)) or
                not math.isfinite(n) for n in value)):
        raise ValueError("reviewed camera pose lacks finite " + name)
    return tuple(float(n) for n in value)


def validate_plan(packet_path: Path) -> list[dict]:
    packet = json.loads(Path(packet_path).read_bytes())
    cameras = packet.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError("reviewed four-view camera plan missing")
    result = []
    for expected, item in zip(VIEWS, cameras):
        name, width, height = expected
        if (item.get("name") != name or item.get("width") != width or
                item.get("height") != height or item.get("attachment") not in ("world", "ego") or
                not item.get("pose_source_citation") or not item.get("reviewer")):
            raise ValueError("reviewed camera identity, size or source differs")
        location = _triplet(item.get("location_xyz_m"), name + " location")
        rotation = _triplet(item.get("rotation_rpy_deg"), name + " rotation")
        fov = item.get("fov_deg")
        if isinstance(fov, bool) or not isinstance(fov, (int, float)) or not 1 <= fov <= 170:
            raise ValueError("reviewed camera field of view invalid")
        result.append(dict(item, location_xyz_m=location, rotation_rpy_deg=rotation))
    return result


class CameraRig:
    def __init__(self, world, ego, packet_path: Path, output_root: Path, transform_factory):
        plan = validate_plan(packet_path)
        settings = world.get_settings()
        if (settings.synchronous_mode is not True or settings.no_rendering_mode is not False or
                abs(settings.fixed_delta_seconds - .05) > 1e-9):
            raise ValueError("rendered synchronous 20 Hz world required for original RGB")
        output_setting = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
        if not output_setting:
            raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT is required for Native pixels")
        private = Path(output_setting).resolve()
        if ".runtime-work" not in private.parts:
            raise ValueError("Native output root must be under .runtime-work")
        self.output_root = Path(output_root).resolve()
        if not self.output_root.is_relative_to(private):
            raise ValueError("original camera pixels must stay under .runtime-work")
        if self.output_root.exists() and any(self.output_root.iterdir()):
            raise ValueError("retain previous original camera bytes")
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.condition = Condition()
        self.pending = {}
        self.errors = []
        self.sensors = []
        blueprints = world.get_blueprint_library()
        try:
            for camera in plan:
                blueprint = blueprints.find("sensor.camera.rgb")
                for key, value in (("image_size_x", camera["width"]),
                                   ("image_size_y", camera["height"]),
                                   ("fov", camera["fov_deg"]), ("sensor_tick", "0.0")):
                    blueprint.set_attribute(key, str(value))
                transform = transform_factory(camera["location_xyz_m"], camera["rotation_rpy_deg"])
                kwargs = {"attach_to": ego} if camera["attachment"] == "ego" else {}
                sensor = world.spawn_actor(blueprint, transform, **kwargs)
                self.sensors.append(sensor)
                sensor.listen(lambda image, name=camera["name"], width=camera["width"],
                              height=camera["height"]: self._receive(name, width, height, image))
        except Exception:
            self.close()
            raise

    def _receive(self, name, width, height, image):
        try:
            frame, timestamp = image.frame, float(image.timestamp)
            data = bytes(image.raw_data)
            if (isinstance(frame, bool) or not isinstance(frame, int) or frame < 0 or
                    not math.isfinite(timestamp) or image.width != width or
                    image.height != height or len(data) != width * height * 4):
                raise ValueError("original RGB frame, time, size or raw pixels differ")
            folder = self.output_root / name
            folder.mkdir(exist_ok=True)
            path = folder / f"{frame:08d}.bgra"
            with path.open("xb") as stream:
                stream.write(data)
            item = {"frame": frame, "time_s": timestamp, "width": width,
                    "height": height, "raw_bgra": str(path.relative_to(self.output_root)),
                    "sha256": hashlib.sha256(data).hexdigest()}
            with self.condition:
                key = (name, frame)
                if key in self.pending:
                    raise ValueError("duplicate original RGB frame")
                self.pending[key] = item
                self.condition.notify_all()
        except Exception as error:
            with self.condition:
                self.errors.append(error)
                self.condition.notify_all()

    def await_frame(self, frame: int, time_s: float, timeout_s: float = 10.0):
        deadline = time.monotonic() + timeout_s
        with self.condition:
            while not self.errors and any((name, frame) not in self.pending for name, _, _ in VIEWS):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("original four-camera frame missing")
                self.condition.wait(remaining)
            if self.errors:
                raise ValueError("original camera callback failed: " + str(self.errors[0]))
            result = {name: self.pending.pop((name, frame)) for name, _, _ in VIEWS}
        if any(abs(item["time_s"] - time_s) > .05 for item in result.values()):
            raise ValueError("original camera and world timestamps differ")
        return result

    def close(self):
        for sensor in self.sensors:
            sensor.stop()
            sensor.destroy()
        self.sensors.clear()
