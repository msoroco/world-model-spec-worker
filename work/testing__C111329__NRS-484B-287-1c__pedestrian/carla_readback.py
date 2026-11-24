"""Lazy CARLA readback bridge for exact site observations.

Callers own actor creation and cleanup. Operation is supplied from an original
device-health source; a displayed traffic-light color alone cannot establish it.
"""

from __future__ import annotations

from collections import deque
from io import BytesIO

from PIL import Image

from native_observation import CAMERAS, CAMERA_DIMENSIONS


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


def device_reader(packet, actors, operation_readback):
    """Bind each source device ID to its own CARLA actor and health readback."""
    expected = {d["device_id"] for d in packet["devices"]}
    if set(actors) != expected or not callable(operation_readback):
        raise ValueError("source-bound device actors and operation reader required")
    actor_ids = [a.id for a in actors.values()]
    if (any(type(actor_id) is not int or actor_id < 0 for actor_id in actor_ids)
            or len(set(actor_ids)) != len(actor_ids)):
        raise ValueError("distinct original device actor identities required")

    def read(device_id):
        if device_id not in expected:
            raise ValueError("unknown source device ID")
        actor = actors[device_id]
        state = str(actor.get_state())
        operating = operation_readback(device_id, actor)
        if not state or type(operating) is not bool:
            raise ValueError("original device state or operation unavailable")
        return {"device_id": device_id, "actor_id": actor.id,
                "state": state, "is_operating": operating}

    return read
