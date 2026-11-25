"""Lazy CARLA frame and vehicle body bridges for original roundabout capture."""

from __future__ import annotations

from collections import deque
from io import BytesIO

from PIL import Image

from capture_roundabout import CAMERAS, CAMERA_DIMENSIONS


class CameraFrames:
    """Join four CARLA BGRA callbacks to the frame returned by world.tick()."""

    def __init__(self, dimensions=None, *, max_pending=4):
        self.dimensions = dict(dimensions or CAMERA_DIMENSIONS)
        if set(self.dimensions) != set(CAMERAS):
            raise ValueError("four named camera dimensions required")
        if not isinstance(max_pending, int) or max_pending < 1:
            raise ValueError("positive camera buffer bound required")
        self.max_pending = max_pending
        self.pending = {name: {} for name in CAMERAS}
        self.order = {name: deque() for name in CAMERAS}

    def callback(self, name):
        if name not in self.pending:
            raise ValueError("unknown camera name")

        def receive(image):
            frame = int(image.frame)
            width, height = self.dimensions[name]
            if (image.width, image.height) != (width, height):
                raise ValueError("original camera dimensions mismatch")
            raw = bytes(image.raw_data)
            if len(raw) != width * height * 4:
                raise ValueError("original BGRA byte count mismatch")
            if frame in self.pending[name]:
                raise ValueError("duplicate original camera frame")
            decoded = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA").convert("RGB")
            stream = BytesIO()
            decoded.save(stream, format="PNG")
            self.pending[name][frame] = stream.getvalue()
            self.order[name].append(frame)
            if len(self.order[name]) > self.max_pending:
                old = self.order[name].popleft()
                del self.pending[name][old]

        return receive

    def reader(self, name):
        if name not in self.pending:
            raise ValueError("unknown camera name")

        def read(frame):
            if frame not in self.pending[name]:
                raise ValueError("original camera frame unavailable")
            self.order[name].remove(frame)
            return {"frame": frame, "png_bytes": self.pending[name].pop(frame)}

        return read

    def readers(self):
        return {name: self.reader(name) for name in CAMERAS}


def body_vertices(actor):
    """Read eight current world-space CARLA bounding-box vertices."""
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    return [[float(point.x), float(point.y), float(point.z)] for point in points]
