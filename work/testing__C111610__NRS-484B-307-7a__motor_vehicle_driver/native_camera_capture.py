"""Capture four original PNG views on the same tick as arrow and actor events."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from aspect_capture import AspectError
from event_capture import capture_pair

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
PRODUCTION_DIMS = {"overview": (1920, 1080), "approach": (1280, 720),
                   "reference_corner": (1280, 720),
                   "driver_reference": (1280, 720)}


def capture_with_cameras(site, attempt_root, step, *, frames=900,
                         diagnostic=False, dimensions=None):
    root = Path(attempt_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    dims = PRODUCTION_DIMS if dimensions is None else dimensions
    if set(dims) != set(CAMERAS) or (not diagnostic and dims != PRODUCTION_DIMS):
        raise AspectError("exact four-camera production profile required")
    paths = {name: root / (name + ".png.zip") for name in CAMERAS}
    receipt_path = root / "arrow-camera-receipt.json"
    if receipt_path.exists() or any(path.exists() for path in paths.values()):
        raise AspectError("original camera source already exists")
    archives = {name: ZipFile(path, "w", compression=ZIP_STORED)
                for name, path in paths.items()}
    try:
        def sampled(index):
            item = step(index)
            if not isinstance(item, tuple) or len(item) != 3:
                raise AspectError("Native tick must supply aspect, actor and four cameras")
            aspect, event, images = item
            if not isinstance(images, dict) or set(images) != set(CAMERAS):
                raise AspectError("four original camera packets missing")
            for name in CAMERAS:
                image = images[name]
                if (not isinstance(image, dict) or image.get("frame") != aspect.get("frame")
                        or not isinstance(image.get("png_bytes"), bytes)):
                    raise AspectError("original camera frame mismatch: " + name)
                raw = image["png_bytes"]
                with Image.open(io.BytesIO(raw)) as pixels:
                    if pixels.format != "PNG" or pixels.size != tuple(dims[name]):
                        raise AspectError("original camera PNG profile mismatch: " + name)
                    pixels.load()
                archives[name].writestr(f"{aspect['frame']:08d}.png", raw)
            return aspect, event
        event_receipt = capture_pair(site, root, sampled, frames=frames,
                                     diagnostic=diagnostic)
        for archive in archives.values():
            archive.close()
        camera_sources = {name: {"path": paths[name].name,
                                 "sha256": hashlib.sha256(paths[name].read_bytes()).hexdigest(),
                                 "dimensions": list(dims[name]), "frame_count": frames}
                          for name in CAMERAS}
        receipt = {"format": "c111610-original-arrow-cameras-v1",
                   "event_sha256": event_receipt["event_ref"]["sha256"],
                   "aspect_sha256": event_receipt["aspect_sha256"],
                   "frame_count": frames, "diagnostic": diagnostic,
                   "camera_sources": camera_sources,
                   "physical_acceptance": False}
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n")
        return receipt
    except BaseException:
        for archive in archives.values():
            archive.close()
        for path in (*paths.values(), receipt_path):
            path.unlink(missing_ok=True)
        raise
