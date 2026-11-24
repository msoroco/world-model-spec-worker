"""Independently decode the four original arrow-camera archives."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from aspect_capture import AspectError
from native_camera_capture import CAMERAS, PRODUCTION_DIMS
from saved_aspect import join_event_history


def audit(site, attempt_root, *, diagnostic=False, dimensions=None):
    root = Path(attempt_root).resolve()
    dims = PRODUCTION_DIMS if dimensions is None else dimensions
    if not diagnostic and dims != PRODUCTION_DIMS:
        raise AspectError("exact production camera dimensions required")
    receipt = json.loads((root / "arrow-camera-receipt.json").read_text())
    event_receipt = json.loads((root / "arrow-event-receipt.json").read_text())
    if (receipt.get("format") != "c111610-original-arrow-cameras-v1" or
            receipt.get("diagnostic") is not diagnostic or
            receipt.get("event_sha256") != event_receipt.get("event_ref", {}).get("sha256") or
            receipt.get("aspect_sha256") != event_receipt.get("aspect_sha256")):
        raise AspectError("original camera receipt is not bound to arrow sources")
    joined = join_event_history(site, root, event_receipt["event_ref"],
                                delivery=not diagnostic)
    rows = json.loads((root / "arrow-events-original.json").read_text())
    if receipt.get("frame_count") != len(rows) or set(receipt.get("camera_sources", {})) != set(CAMERAS):
        raise AspectError("original four-camera frame count or source inventory missing")
    for name in CAMERAS:
        ref = receipt["camera_sources"][name]
        path = (root / str(ref.get("path", ""))).resolve()
        if path.parent != root or not path.is_file() or path.name != name + ".png.zip":
            raise AspectError("original camera source path invalid: " + name)
        if (hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256") or
                ref.get("frame_count") != len(rows) or
                ref.get("dimensions") != list(dims[name])):
            raise AspectError("original camera source hash or profile mismatch: " + name)
        members = [f"{row['frame']:08d}.png" for row in rows]
        with ZipFile(path) as archive:
            if archive.namelist() != members:
                raise AspectError("original camera frame map mismatch: " + name)
            for member in members:
                raw = archive.read(member)
                with Image.open(io.BytesIO(raw)) as pixels:
                    if pixels.format != "PNG" or pixels.size != tuple(dims[name]):
                        raise AspectError("original camera PNG profile mismatch: " + name)
                    pixels.load()
    return {"format": "c111610-saved-arrow-camera-audit-v1",
            "original_event_sha256": joined["original_event_sha256"],
            "original_aspect_sha256": joined["original_aspect_sha256"],
            "decoded_frames": len(rows), "decoded_images": len(rows) * len(CAMERAS),
            "physical_acceptance": False, "legal_verdict": None}
