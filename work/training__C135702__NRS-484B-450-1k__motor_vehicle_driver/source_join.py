"""Join original obstruction samples to four camera and video frame identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FRAMES = 600


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing required original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root: Path, source_kind: str = "original_native") -> dict:
    root = Path(root)
    names = ("native_samples.jsonl", "video_frames.jsonl", "camera-frames.jsonl")
    samples, frame_map, cameras = (_rows(root / name) for name in names)
    if len(samples) != FRAMES or len(frame_map) != FRAMES or len(cameras) != FRAMES * len(VIEWS):
        raise ValueError("Incomplete 600-frame four-camera source")
    camera_lookup = {(row.get("frame"), row.get("camera")): row for row in cameras}
    if len(camera_lookup) != len(cameras):
        raise ValueError("Duplicate original camera identity")
    for index, (sample, mapping) in enumerate(zip(samples, frame_map)):
        native = sample.get("native_frame")
        if type(native) is not int or native < 0 or mapping.get("native_frame") != native:
            raise ValueError("Original Native frame join differs")
        if mapping.get("video_frame") != index or abs(float(sample.get("time_s", -1)) - index / 20) > 1e-7 or abs(float(mapping.get("time_s", -1)) - index / 20) > 1e-7:
            raise ValueError("Original time/video frame join differs")
        if source_kind == "original_native" and sample.get("source_kind") != "original_native":
            raise ValueError("Original Native sample provenance missing")
        camera_map = mapping.get("camera_native_frames")
        if camera_map != {name: native for name in VIEWS}:
            raise ValueError("Original camera frame map differs")
        for view in VIEWS:
            row = camera_lookup.get((index, view))
            if row is None or row.get("native_frame") != native:
                raise ValueError("Missing original camera source join")
            digest = row.get("rgb_sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("Original camera pixel digest absent")
            if source_kind == "original_native" and row.get("source_kind") != "original_native":
                raise ValueError("Original camera provenance missing")
    return {"passed": True, "frames": FRAMES, "camera_frames": len(cameras),
            "source_kind": source_kind, "source_sha256": {name: _sha(root / name) for name in names},
            "original_pixels_decoded": False, "physical_cause_confirmed": False,
            "legal_verdict_claimed": False}
