"""Independently decode four original roundabout camera streams against motion."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from capture_roundabout import CAMERAS, CAMERA_DIMENSIONS
from roundabout_measurements import measure


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_saved(*, case_id, map_path, trace_path, receipt_path,
                required_frames=900, camera_dimensions=None):
    """Require source-bound motion and every decoded, frame-matched PNG."""
    motion = measure(case_id=case_id, map_path=map_path,
                     trace_path=trace_path, receipt_path=receipt_path)
    receipt_file = Path(receipt_path).resolve()
    receipt = json.loads(receipt_file.read_text())
    if receipt.get("case_id") != case_id or receipt.get("frame_count") != required_frames:
        raise ValueError("exact camera case and frame count required")
    if receipt.get("camera_capture_complete") is not True:
        raise ValueError("original four-camera capture missing")
    sources = receipt.get("camera_sources")
    if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
        raise ValueError("original four-camera sources missing")
    dimensions = camera_dimensions or CAMERA_DIMENSIONS
    if set(dimensions) != set(CAMERAS):
        raise ValueError("four named camera dimensions required")
    rows = [json.loads(line) for line in Path(trace_path).read_text().splitlines()]
    if len(rows) != required_frames:
        raise ValueError("original motion frame count mismatch")
    for name in CAMERAS:
        ref = sources[name]
        path = (receipt_file.parent / ref["path"]).resolve()
        if path.parent != receipt_file.parent or _sha(path) != ref["sha256"]:
            raise ValueError(f"{name} original camera source hash mismatch")
        if ref.get("frame_count") != required_frames or ref.get("dimensions") != list(dimensions[name]):
            raise ValueError(f"{name} original camera profile mismatch")
        members = [f"{row['frame']:08d}.png" for row in rows]
        with ZipFile(path) as archive:
            if archive.namelist() != members:
                raise ValueError(f"{name} original camera frame map mismatch")
            for row, member in zip(rows, members):
                payload = archive.read(member)
                if row.get("camera_frames", {}).get(name) != {
                        "member": member, "sha256": hashlib.sha256(payload).hexdigest()}:
                    raise ValueError(f"{name} original camera pixel binding mismatch")
                with Image.open(BytesIO(payload)) as image:
                    image.verify()
                with Image.open(BytesIO(payload)) as image:
                    if image.format != "PNG" or image.size != tuple(dimensions[name]):
                        raise ValueError(f"{name} original camera image mismatch")
                    image.load()
    return {"format": "worker-original-roundabout-camera-audit",
            "case_id": case_id, "frame_count": required_frames,
            "decoded_images": required_frames * len(CAMERAS),
            "camera_source_sha256": {name: sources[name]["sha256"] for name in CAMERAS},
            "motion": motion, "physical_acceptance": False, "legal_verdict": None}
