"""Independent audit of original Native camera sources for a saved attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

CAMERAS = ("front", "left", "right", "rear")
PROFILE_DIMENSIONS = {"front": (1920, 1080), "left": (1280, 720),
                      "right": (1280, 720), "rear": (1280, 720)}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(manifest_path: Path, *, expected_frames: int = 900,
          dimensions: dict | None = None) -> dict:
    """Decode every original PNG and reject missing, duplicated or rebound frames.

    Smaller expected_frames and dimensions are only for CPU unit fixtures. A
    production receipt always uses 900 and the four capture profile sizes.
    """
    dimensions = PROFILE_DIMENSIONS if dimensions is None else dimensions
    root = manifest_path.resolve().parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("original_frame_count") != expected_frames:
        raise ValueError("original frame count mismatch")
    entry = manifest.get("original_media_map")
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError("original media map missing")
    map_path = (root / entry["path"]).resolve()
    if not map_path.is_relative_to(root) or not map_path.is_file() or _hash(map_path) != entry.get("sha256"):
        raise ValueError("original media map source mismatch")
    media = json.loads(map_path.read_text(encoding="utf-8"))
    if len(media) != expected_frames * len(CAMERAS):
        raise ValueError("original camera count mismatch")
    seen = set()
    frames = set()
    for item in media:
        frame, camera = item.get("frame"), item.get("camera")
        if not isinstance(frame, int) or camera not in CAMERAS or (frame, camera) in seen:
            raise ValueError("duplicate or invalid camera frame")
        seen.add((frame, camera))
        frames.add(frame)
        path = (root / item.get("path", "")).resolve()
        if not path.is_relative_to(root) or path != root / camera / f"{frame:08d}.png":
            raise ValueError("camera frame path rebound")
        if not path.is_file() or _hash(path) != item.get("sha256"):
            raise ValueError("original camera source mismatch")
        with Image.open(path) as image:
            if image.format != "PNG" or image.size != tuple(dimensions[camera]):
                raise ValueError("camera format or dimensions mismatch")
            image.load()
    if sorted(frames) != list(range(min(frames), min(frames) + expected_frames)):
        raise ValueError("original camera frame sequence discontinuity")
    if seen != {(frame, camera) for frame in frames for camera in CAMERAS}:
        raise ValueError("original camera join incomplete")
    return {"passed": True, "original_frames": expected_frames,
            "decoded_original_pngs": len(media), "media_map_sha256": entry["sha256"],
            "physical_visibility_reviewed": False}
