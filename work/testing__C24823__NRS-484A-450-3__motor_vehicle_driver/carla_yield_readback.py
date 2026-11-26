"""Lazy CARLA frame and vehicle body bridges for original yield capture."""

from __future__ import annotations

from collections import deque
from io import BytesIO
from threading import Condition
from time import monotonic

from PIL import Image

from yield_source import CAMERAS, DIMENSIONS as CAMERA_DIMENSIONS


class CameraFrames:
    """Join four CARLA BGRA callbacks to the frame returned by world.tick()."""

    def __init__(self, dimensions=None, *, max_pending=4, frame_timeout_s=10):
        self.dimensions = dict(dimensions or CAMERA_DIMENSIONS)
        if set(self.dimensions) != set(CAMERAS):
            raise ValueError("four named camera dimensions required")
        if not isinstance(max_pending, int) or max_pending < 1:
            raise ValueError("positive camera buffer bound required")
        if not isinstance(frame_timeout_s, (int, float)) or frame_timeout_s <= 0:
            raise ValueError("positive camera frame timeout required")
        self.max_pending = max_pending
        self.frame_timeout_s = float(frame_timeout_s)
        self.condition = Condition()
        self.errors = {name: None for name in CAMERAS}
        self.pending = {name: {} for name in CAMERAS}
        self.order = {name: deque() for name in CAMERAS}

    def callback(self, name):
        if name not in self.pending:
            raise ValueError("unknown camera name")

        def receive(image):
            try:
                frame = int(image.frame)
                width, height = self.dimensions[name]
                if (image.width, image.height) != (width, height):
                    raise ValueError("original camera dimensions mismatch")
                raw = bytes(image.raw_data)
                if len(raw) != width * height * 4:
                    raise ValueError("original BGRA byte count mismatch")
                decoded = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA").convert("RGB")
                stream = BytesIO()
                decoded.save(stream, format="PNG")
                with self.condition:
                    if frame in self.pending[name]:
                        raise ValueError("duplicate original camera frame")
                    self.pending[name][frame] = stream.getvalue()
                    self.order[name].append(frame)
                    if len(self.order[name]) > self.max_pending:
                        old = self.order[name].popleft()
                        del self.pending[name][old]
                    self.condition.notify_all()
            except BaseException as error:
                with self.condition:
                    self.errors[name] = error
                    self.condition.notify_all()

        return receive

    def reader(self, name):
        if name not in self.pending:
            raise ValueError("unknown camera name")

        def read(frame):
            deadline = monotonic() + self.frame_timeout_s
            with self.condition:
                while frame not in self.pending[name]:
                    if self.errors[name] is not None:
                        raise ValueError("original camera callback failed") from self.errors[name]
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise ValueError("original camera frame unavailable")
                    self.condition.wait(remaining)
                self.order[name].remove(frame)
                return {"frame": frame, "png_bytes": self.pending[name].pop(frame)}

        return read

    def readers(self):
        return {name: self.reader(name) for name in CAMERAS}


def body_vertices(actor):
    """Read eight current world-space CARLA bounding-box vertices."""
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    return [[float(point.x), float(point.y), float(point.z)] for point in points]
