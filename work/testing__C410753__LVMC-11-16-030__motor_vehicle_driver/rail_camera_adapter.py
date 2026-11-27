"""Lazy CARLA camera adapter for the four original railway capture streams.

The operator spawns and owns the sensors. This adapter only attaches callbacks,
checks original sensor identity and converts CARLA BGRA bytes to lossless PNG.
"""
from __future__ import annotations

from io import BytesIO
from math import isfinite
from queue import Empty, Full, Queue
from typing import Any

from rail_native_capture import CAMERAS


class CameraAdapter:
    def __init__(self, sensors: dict[str, Any], timeout_s: float = 5.0):
        if not isinstance(sensors, dict) or set(sensors) != set(CAMERAS):
            raise ValueError("four named CARLA sensor actors required")
        if not isinstance(timeout_s, (int, float)) or not isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("sensor timeout invalid")
        self.sensors = sensors
        self.timeout_s = float(timeout_s)
        self.queues = {name: Queue(maxsize=2) for name in CAMERAS}
        self.overflow = set()
        self.started = False

    def start(self) -> None:
        if self.started:
            raise ValueError("sensor adapter already started")
        attached = []
        try:
            for name, sensor in self.sensors.items():
                def receive(image, channel=name):
                    try:
                        self.queues[channel].put_nowait(image)
                    except Full:
                        self.overflow.add(channel)
                sensor.listen(receive)
                attached.append(sensor)
            self.started = True
        except BaseException:
            for sensor in reversed(attached):
                sensor.stop()
            raise

    def read(self, frame: int, snapshot: Any) -> dict[str, tuple[int, bytes]]:
        if not self.started:
            raise ValueError("sensor adapter not started")
        if self.overflow:
            raise ValueError("original camera sensor queue overflow")
        from PIL import Image
        result = {}
        for name, dimensions in CAMERAS.items():
            try:
                image = self.queues[name].get(timeout=self.timeout_s)
            except Empty as exc:
                raise ValueError(f"{name} original camera frame missing") from exc
            if image.frame != frame:
                raise ValueError(f"{name} original camera frame identity differs")
            time_s = image.timestamp
            if not isinstance(time_s, (int, float)) or not isfinite(time_s):
                raise ValueError(f"{name} original camera timestamp invalid")
            if abs(time_s - snapshot.timestamp.elapsed_seconds) > 0.001:
                raise ValueError(f"{name} original camera timestamp differs")
            if (image.width, image.height) != dimensions:
                raise ValueError(f"{name} original camera dimensions differ")
            raw = bytes(image.raw_data)
            if len(raw) != dimensions[0] * dimensions[1] * 4:
                raise ValueError(f"{name} original BGRA byte count differs")
            rgb = Image.frombytes("RGBA", dimensions, raw, "raw", "BGRA").convert("RGB")
            stream = BytesIO()
            rgb.save(stream, format="PNG")
            result[name] = (frame, stream.getvalue())
        return result

    def stop(self) -> None:
        if self.started:
            for sensor in self.sensors.values():
                sensor.stop()
        self.started = False
