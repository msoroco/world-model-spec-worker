"""Independently decode and bind all original 20 Hz camera frames to motion."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from native_observation import CAMERAS, CAMERA_DIMENSIONS, analyze_saved


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_saved(packet: dict, receipt: dict, *, expected_case_id: str,
                required_frames: int = 900, camera_dimensions=None) -> dict:
    """Require four complete, original, decoded PNG streams for an exact case."""
    motion = analyze_saved(packet, receipt, expected_case_id=expected_case_id,
                           required_frames=required_frames)
    if receipt.get("camera_capture_complete") is not True:
        raise ValueError("original four-camera capture missing")
    observation = Path(receipt["path"]).resolve()
    document = json.loads(observation.read_text())
    rows = document["frames"]
    sources = document.get("camera_sources")
    if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
        raise ValueError("original four-camera sources missing")
    dimensions = camera_dimensions or CAMERA_DIMENSIONS
    if set(dimensions) != set(CAMERAS):
        raise ValueError("four named camera dimensions required")
    for name in CAMERAS:
        ref = sources[name]
        path = Path(ref["path"]).resolve()
        if path.parent != observation.parent or _sha(path) != ref["sha256"]:
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
    return {"format": "worker-original-pedestrian-camera-audit",
            "case_id": expected_case_id, "frame_count": required_frames,
            "decoded_images": required_frames * len(CAMERAS),
            "camera_source_sha256": {name: sources[name]["sha256"] for name in CAMERAS},
            "motion": motion, "physical_acceptance": False, "legal_verdict": None}
