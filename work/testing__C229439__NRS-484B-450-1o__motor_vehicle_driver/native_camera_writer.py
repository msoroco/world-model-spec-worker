"""Join four original CARLA RGB callbacks to 900 world ticks and seal PNGs.

The caller owns sensor placement and must separately review sign visibility.
This module never substitutes generated pixels for Native callback data.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import queue
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image


DIMENSIONS = {"front": (1920, 1080), "rear": (1280, 720),
              "left": (1280, 720), "right": (1280, 720)}


def _png(image, dimensions):
    width, height = dimensions
    if (image.width, image.height) != (width, height):
        raise ValueError("original camera dimensions mismatch")
    raw = bytes(image.raw_data)
    if len(raw) != width * height * 4:
        raise ValueError("original camera BGRA byte count mismatch")
    output = io.BytesIO()
    Image.frombytes("RGB", (width, height), raw, "raw", "BGRX").save(output, format="PNG")
    return output.getvalue()


class NativeCameraWriter:
    def __init__(self, sensors, output_root, dimensions=None):
        self.dimensions = DIMENSIONS if dimensions is None else dimensions
        if set(sensors) != set(DIMENSIONS) or set(self.dimensions) != set(DIMENSIONS):
            raise ValueError("four named original RGB cameras required")
        self.root = Path(output_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.queues = {name: queue.Queue(maxsize=4) for name in DIMENSIONS}
        self.archives = {}
        self.last_frame = None
        self.first_frame = None
        self.count = 0
        for name, sensor in sensors.items():
            if getattr(sensor, "type_id", None) != "sensor.camera.rgb":
                raise ValueError("original RGB sensor required")
            attrs = sensor.attributes
            width, height = self.dimensions[name]
            if (str(attrs.get("image_size_x")), str(attrs.get("image_size_y"))) != (str(width), str(height)):
                raise ValueError("sensor profile differs")
            self.archives[name] = ZipFile(self.root / (name + ".png.zip"), "w", compression=ZIP_STORED)
            sensor.listen(self.queues[name].put)

    def capture(self, snapshot):
        frame = snapshot.frame
        stamp = snapshot.timestamp.elapsed_seconds
        if not isinstance(frame, int) or not math.isfinite(stamp):
            raise ValueError("original world frame and timestamp required")
        if self.last_frame is not None and frame != self.last_frame + 1:
            raise ValueError("world frame sequence mismatch")
        if self.count >= 900:
            raise ValueError("900-frame capture exceeded")
        bindings = {}
        for name in DIMENSIONS:
            image = self.queues[name].get(timeout=5)
            if image.frame != frame or abs(image.timestamp - stamp) > 0.001:
                raise ValueError("camera callback frame or timestamp mismatch")
            payload = _png(image, self.dimensions[name])
            member = f"{frame:08d}.png"
            self.archives[name].writestr(member, payload)
            bindings[name] = {"member": member, "sha256": hashlib.sha256(payload).hexdigest()}
        self.first_frame = frame if self.first_frame is None else self.first_frame
        self.last_frame = frame
        self.count += 1
        return bindings

    def close(self):
        for archive in self.archives.values():
            archive.close()
        if self.count != 900:
            raise ValueError("original 900-frame capture incomplete")
        refs = {}
        for name in DIMENSIONS:
            path = self.root / (name + ".png.zip")
            refs[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "frame_count": 900, "fps": 20, "dimensions": list(self.dimensions[name])}
        return refs


def seal_rows(root, rows, camera_refs):
    """Write exact frame-map and actor-row hashes after 900 complete ticks."""
    root = Path(root)
    if len(rows) != 900 or set(camera_refs) != set(DIMENSIONS):
        raise ValueError("incomplete original capture")
    mapping = [{"frame": row["frame"], "time_s": row["time_s"]} for row in rows]
    refs = {}
    for name, value in (("actor_rows", rows), ("frame_map", mapping)):
        path = root / (name + ".json")
        path.write_text(json.dumps(value, separators=(",", ":")) + "\n")
        refs[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {**refs, "camera_archives": camera_refs, "cameras": camera_refs}
