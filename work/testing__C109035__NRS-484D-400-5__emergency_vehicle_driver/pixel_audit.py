"""Reopen four original PNG camera archives for one 900-frame Native attempt."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from saved_finalizer import PREFIX, _read
from camera_recorder import PROFILE_SIZES

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def audit_pixels(folder: Path, *, case_id: str, diagnostic: bool = False) -> dict:
    folder = Path(folder)
    receipt_file = folder / "capture_receipt.json"
    if receipt_file.is_symlink():
        raise ValueError("Original capture receipt symlinked")
    receipt_bytes = receipt_file.read_bytes()
    receipt = json.loads(receipt_bytes)
    if not case_id.startswith(PREFIX) or receipt.get("case_id") != case_id:
        raise ValueError("Original pixel case identity mismatch")
    traces = [json.loads(line) for line in _read(folder, receipt["sources"]["camera_trace"]).splitlines()]
    if len(traces) != 900:
        raise ValueError("Original camera trace incomplete")
    manifest_file = folder / "camera_media.json"
    if manifest_file.is_symlink():
        raise ValueError("Original camera media manifest symlinked")
    manifest = json.loads(manifest_file.read_text())
    if (manifest.get("case_id") != case_id or
            manifest.get("capture_receipt_sha256") != hashlib.sha256(receipt_bytes).hexdigest() or
            set(manifest.get("cameras", {})) != set(CAMERAS)):
        raise ValueError("Original camera media inventory incomplete")
    for camera in CAMERAS:
        reference = manifest["cameras"][camera]
        archive_bytes = _read(folder, reference)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Original camera archive has duplicate frame names")
            expected_names = set()
            for tick, trace in enumerate(traces):
                native_frame = receipt["native_first_frame"] + tick
                name = f"{native_frame}.png"
                expected_names.add(name)
                if trace.get("frame") != tick or trace.get("native_frame") != native_frame:
                    raise ValueError("Original camera frame join mismatch")
                if trace.get("sources", {}).get(camera) != reference["path"] + "#" + name:
                    raise ValueError("Original camera source reference mismatch")
                with Image.open(io.BytesIO(archive.read(name))) as image:
                    if image.format != "PNG" or min(image.size) <= 0:
                        raise ValueError("Original camera PNG invalid")
                    if not diagnostic and image.size != PROFILE_SIZES[camera]:
                        raise ValueError("Original camera dimensions differ from capture profile")
                    image.load()
            if set(names) != expected_names:
                raise ValueError("Original camera archive frame inventory mismatch")
    return {"case_id": case_id, "frames_per_camera": 900,
            "decoded_original_pixels": 3600,
            "capture_profile_dimensions_verified": not diagnostic,
            "media_sha256": {camera: manifest["cameras"][camera]["sha256"] for camera in CAMERAS},
            "physical_visibility": "requires_independent_review"}
