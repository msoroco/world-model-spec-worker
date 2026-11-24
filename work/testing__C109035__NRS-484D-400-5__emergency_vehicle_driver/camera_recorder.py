"""Retain synchronized original CARLA camera images for a Native attempt.

The reader supplies the four images for one world frame. This adapter records
their BGRA pixels as lossless PNGs; it does not evaluate physical visibility.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from PIL import Image


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
PROFILE_SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
                 "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


class CameraRecorder:
    """Callable camera adapter for native_capture.capture.

    frame_reader(native_frame) returns a mapping of CARLA Image objects. The
    reader owns sensor queues and must return the requested frame exactly.
    """

    def __init__(self, output: Path, frame_reader, *, case_id: str,
                 source_ids: dict, sizes: dict | None = None, binding=None):
        self.output = Path(output)
        self.frame_reader = frame_reader
        self.case_id = case_id
        self.sizes = sizes or PROFILE_SIZES
        if set(self.sizes) != set(CAMERAS) or set(source_ids) != set(CAMERAS):
            raise ValueError("Four camera dimensions and source IDs required")
        if any(len(size) != 2 or min(size) <= 0 for size in self.sizes.values()):
            raise ValueError("Camera dimensions invalid")
        if not all(isinstance(source_ids[key], str) and source_ids[key] for key in CAMERAS):
            raise ValueError("Camera source ID missing")
        self.source_ids = dict(source_ids)
        self.archives = None
        self.frames = 0
        self.closed = False
        self.binding = binding

    def bind(self, world, ego):
        if self.binding is not None:
            self.binding(world, ego)

    def _open(self):
        self.output.mkdir(parents=True, exist_ok=True)
        if any((self.output / (key + ".zip")).exists() for key in CAMERAS):
            raise ValueError("Original camera archive already exists")
        self.archives = {key: zipfile.ZipFile(self.output / (key + ".zip"), "w",
                         compression=zipfile.ZIP_STORED) for key in CAMERAS}

    def __call__(self, native_frame: int) -> dict:
        if self.closed or type(native_frame) is not int or native_frame < 0:
            raise ValueError("Camera recorder closed or frame invalid")
        images = self.frame_reader(native_frame)
        if not isinstance(images, dict) or set(images) != set(CAMERAS):
            raise ValueError("Four original camera images required")
        encoded = {}
        for key in CAMERAS:
            image = images[key]
            width, height = self.sizes[key]
            if (getattr(image, "frame", None) != native_frame or
                    getattr(image, "width", None) != width or
                    getattr(image, "height", None) != height):
                raise ValueError("Original camera frame or dimensions mismatch: " + key)
            raw = bytes(image.raw_data)
            if len(raw) != width * height * 4:
                raise ValueError("Original BGRA byte count mismatch: " + key)
            rgb = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA").convert("RGB")
            stream = io.BytesIO()
            rgb.save(stream, format="PNG")
            encoded[key] = stream.getvalue()
        if self.archives is None:
            self._open()
        name = f"{native_frame}.png"
        for key in CAMERAS:
            self.archives[key].writestr(name, encoded[key])
        self.frames += 1
        return {key: key + ".zip#" + name for key in CAMERAS}

    def finish(self, receipt: dict) -> dict:
        if self.closed or self.archives is None:
            raise ValueError("Camera recorder has no open capture")
        if receipt.get("case_id") != self.case_id or receipt.get("source_kind") != "original_capture":
            raise ValueError("Original capture receipt identity mismatch")
        first = receipt.get("native_first_frame")
        last = receipt.get("native_last_frame")
        if type(first) is not int or last != first + self.frames - 1 or self.frames != 900:
            raise ValueError("Original camera frame count incomplete")
        for archive in self.archives.values():
            archive.close()
        self.closed = True
        receipt_bytes = (self.output / "capture_receipt.json").read_bytes()
        if json.loads(receipt_bytes) != receipt:
            raise ValueError("Original capture receipt bytes differ")
        media = {"case_id": self.case_id,
                 "capture_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                 "source_ids": self.source_ids,
                 "cameras": {}}
        for key in CAMERAS:
            path = self.output / (key + ".zip")
            media["cameras"][key] = {"path": path.name,
                                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = self.output / "camera_media.json"
        if manifest.exists() or manifest.is_symlink():
            raise ValueError("Original camera manifest already exists")
        manifest.write_text(json.dumps(media, indent=2, sort_keys=True) + "\n")
        return media

    def abort(self) -> None:
        """Close pending archives after a failed Native attempt."""
        if self.archives is not None and not self.closed:
            for archive in self.archives.values():
                archive.close()
        self.closed = True
