"""Acquire four original CARLA RGB streams with exact world-frame joins.

A reviewed site packet must supply the four poses. Raw BGRA samples are retained
under .runtime-work for subsequent lossless encoding and pixel audit.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from threading import Condition
import time

from source_bound_scene import build as bind_scene

VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def _triplet(value, name):
    if not isinstance(value, list) or len(value) != 3 or any(
            type(n) not in (int, float) or not math.isfinite(n) for n in value):
        raise ValueError("camera pose lacks finite " + name)
    return tuple(float(n) for n in value)


def validate_plan(packet_path: Path, suffix: str) -> tuple[dict, list]:
    scene = bind_scene(packet_path, suffix)
    packet = json.loads(Path(packet_path).read_text())
    cameras = packet.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError("reviewed four-camera pose plan missing")
    result = []
    for expected, camera in zip(VIEWS, cameras):
        name, width, height = expected
        if (camera.get("name") != name or camera.get("width") != width or
                camera.get("height") != height or camera.get("attachment") not in ("world", "ego") or
                not camera.get("pose_source_citation") or not camera.get("reviewer")):
            raise ValueError("four-camera source, identity or dimensions differ")
        location = _triplet(camera.get("location_xyz_m"), name + " location")
        rotation = _triplet(camera.get("rotation_rpy_deg"), name + " rotation")
        fov = camera.get("fov_deg")
        if type(fov) not in (int, float) or not 1 <= fov <= 170:
            raise ValueError("camera field of view invalid")
        result.append(dict(camera, location_xyz_m=location, rotation_rpy_deg=rotation))
    return scene, result


class CameraRig:
    def __init__(self, world, ego, packet_path: Path, suffix: str,
                 output_root: Path, transform_factory):
        self.scene, plan = validate_plan(packet_path, suffix)
        settings = world.get_settings()
        if (settings.synchronous_mode is not True or
                settings.no_rendering_mode is not False or
                type(settings.fixed_delta_seconds) not in (int, float) or
                abs(settings.fixed_delta_seconds - .05) > 1e-9):
            raise ValueError("original RGB capture requires rendered synchronous 20 Hz world")
        self.output_root = Path(output_root).resolve()
        source = Path(__file__).resolve()
        private = next((part for part in source.parents if part.name == ".runtime-work"),
                       source.parents[2] / ".runtime-work")
        if self.output_root != private and private not in self.output_root.parents:
            raise ValueError("original camera bytes must stay under .runtime-work")
        if self.output_root.exists() and any(self.output_root.iterdir()):
            raise ValueError("retain previous original camera output")
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.condition = Condition()
        self.pending = {}
        self.errors = []
        self.sensors = []
        blueprints = world.get_blueprint_library()
        try:
            for camera in plan:
                blueprint = blueprints.find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(camera["width"]))
                blueprint.set_attribute("image_size_y", str(camera["height"]))
                blueprint.set_attribute("fov", str(camera["fov_deg"]))
                blueprint.set_attribute("sensor_tick", "0.0")
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
            frame = image.frame
            time_s = float(image.timestamp)
            data = bytes(image.raw_data)
            if (type(frame) is not int or frame < 0 or not math.isfinite(time_s) or
                    image.width != width or image.height != height or len(data) != width * height * 4):
                raise ValueError("original camera sample frame, time, size or pixels differ")
            target = self.output_root / name
            target.mkdir(exist_ok=True)
            path = target / f"{frame:08d}.bgra"
            with path.open("xb") as stream:
                stream.write(data)
            item = {"view": name, "frame": frame, "time_s": time_s,
                    "width": width, "height": height,
                    "raw_bgra": str(path.relative_to(self.output_root)),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "source_packet_sha256": self.scene["source_packet_sha256"]}
            with self.condition:
                key = (name, frame)
                if key in self.pending:
                    raise ValueError("duplicate original camera frame")
                self.pending[key] = item
                self.condition.notify_all()
        except Exception as error:
            with self.condition:
                self.errors.append(error)
                self.condition.notify_all()

    def await_frame(self, frame: int, time_s: float, timeout_s: float = 10.0) -> dict:
        if type(frame) is not int or type(time_s) not in (int, float):
            raise ValueError("Native world frame and time required")
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
        if any(abs(item["time_s"] - time_s) > 0.05 for item in result.values()):
            raise ValueError("camera and Native world timestamps differ")
        return result

    def close(self) -> None:
        for sensor in self.sensors:
            sensor.stop()
            sensor.destroy()
        self.sensors.clear()
