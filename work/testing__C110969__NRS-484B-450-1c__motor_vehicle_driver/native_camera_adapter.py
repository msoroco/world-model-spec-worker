"""Consume four existing Native RGB camera sensors at the just-ticked frame.

Sensor placement and visibility must be reviewed separately. This adapter only
converts original callback BGRA bytes into lossless PNGs and joins frame IDs.
"""
from __future__ import annotations

import io
import threading
import time

from PIL import Image

from intersection_observables import _require
from native_media import CAMERAS


class NativeCameraAdapter:
    def __init__(self, sensors: dict, *, timeout_s: float = 2.0):
        _require(set(sensors) == set(CAMERAS), "four exact Native cameras required")
        _require(timeout_s > 0, "camera callback timeout must be positive")
        self.sensors = dict(sensors)
        self.timeout_s = timeout_s
        self.condition = threading.Condition()
        self.pending = {key: {} for key in CAMERAS}
        self.last_frame = None
        self.closed = False
        for key, sensor in self.sensors.items():
            _require(getattr(sensor, "type_id", None) == "sensor.camera.rgb",
                     "Native RGB camera required: " + key)
            attrs = getattr(sensor, "attributes", {})
            width, height = CAMERAS[key]
            _require(str(attrs.get("image_size_x")) == str(width) and
                     str(attrs.get("image_size_y")) == str(height),
                     "Native camera dimensions differ: " + key)
            sensor.listen(lambda image, name=key: self._receive(name, image))

    def _receive(self, name, image):
        with self.condition:
            if self.closed:
                return
            frame = getattr(image, "frame", None)
            if not isinstance(frame, int):
                return
            if self.last_frame is not None and frame <= self.last_frame:
                return
            self.pending[name][frame] = image
            self.condition.notify_all()

    def capture(self, snapshot, actor):
        del actor
        frame = snapshot.frame
        _require(isinstance(frame, int), "Native snapshot frame required")
        deadline = time.monotonic() + self.timeout_s
        with self.condition:
            _require(not self.closed and
                     (self.last_frame is None or frame == self.last_frame + 1),
                     "Native camera frame sequence differs")
            while not all(frame in self.pending[key] for key in CAMERAS):
                remaining = deadline - time.monotonic()
                _require(remaining > 0, "missing original Native camera callback")
                self.condition.wait(remaining)
            images = {key: self.pending[key][frame] for key in CAMERAS}
        result = {}
        for key, image in images.items():
            width, height = CAMERAS[key]
            _require((image.width, image.height) == (width, height),
                     "Native callback dimensions differ: " + key)
            raw = bytes(image.raw_data)
            _require(len(raw) == width * height * 4,
                     "Native callback BGRA byte count differs: " + key)
            rgb = Image.frombytes("RGB", (width, height), raw, "raw", "BGRX")
            output = io.BytesIO()
            rgb.save(output, format="PNG")
            result[key] = {"frame": frame,
                           "source": "original_native_camera_callback",
                           "png": output.getvalue()}
        with self.condition:
            _require(not self.closed and
                     (self.last_frame is None or frame == self.last_frame + 1),
                     "Native camera frame sequence differs")
            for values in self.pending.values():
                for old in [number for number in values if number <= frame]:
                    del values[old]
            self.last_frame = frame
        return result

    def close(self):
        with self.condition:
            self.closed = True
            for values in self.pending.values():
                values.clear()
            self.condition.notify_all()
        for sensor in self.sensors.values():
            sensor.stop()
