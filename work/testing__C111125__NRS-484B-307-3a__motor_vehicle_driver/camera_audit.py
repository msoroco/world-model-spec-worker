"""Saved-only audit of original, synchronized four-camera PNG sources.

The manifest is an acquisition record, not a claim that physical bodies or the
simultaneous signal indications are visible. The latter needs human review.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from PIL import Image

from dual_green import read_source, require

CAMERAS = {
    "overview": (1920, 1080),
    "approach": (1280, 720),
    "reference_corner": (1280, 720),
    "driver_reference": (1280, 720),
}


def audit_cameras(attempt_dir, expected_case_id, dimensions=None, expected_frames=900):
    """Decode every original image and join acquisition frame identities.

    ``dimensions`` and ``expected_frames`` are injectable for small CPU fixtures;
    delivery callers use the fixed production defaults.
    """
    root = Path(attempt_dir)
    receipt = json.loads((root / "native-attempt.json").read_text(encoding="utf-8"))
    require(receipt["case_id"] == expected_case_id, "camera attempt case mismatch")
    require(receipt["sample_hz"] == 20, "camera sample rate mismatch")
    require(receipt["frame_count"] == expected_frames, "camera duration mismatch")
    events = json.loads(read_source(root, receipt["event_source"]).read_text(encoding="utf-8"))
    require(len(events) == expected_frames, "camera event count mismatch")
    manifest = json.loads(read_source(root, receipt["camera_manifest_source"]).read_text(encoding="utf-8"))
    require(manifest["case_id"] == expected_case_id, "camera manifest case mismatch")
    require(manifest["sample_hz"] == 20, "camera manifest rate mismatch")
    require(manifest["profile_version"] == "overview1080-capability", "camera profile mismatch")
    rows = manifest["frames"]
    require(len(rows) == expected_frames, "camera manifest frame count mismatch")
    expected_dimensions = dimensions if dimensions is not None else CAMERAS
    require(set(expected_dimensions) == set(CAMERAS), "camera names mismatch")
    seen_paths = set()
    seen_frame_ids = set()
    for index, (event, row) in enumerate(zip(events, rows)):
        frame = event["frame"]
        require(type(frame) is int and frame not in seen_frame_ids, "camera duplicate frame")
        seen_frame_ids.add(frame)
        require(row["video_frame"] == index and row["carla_frame"] == frame,
                "camera frame map mismatch")
        require(abs(float(row["time_s"]) - float(event["elapsed_seconds"])) <= 1e-4,
                "camera timestamp mismatch")
        sources = row["views"]
        require(set(sources) == set(CAMERAS), "camera view missing or extra")
        for name, ref in sources.items():
            path = read_source(root, ref)
            require(ref["path"] not in seen_paths, "camera source reused across frames")
            seen_paths.add(ref["path"])
            with Image.open(io.BytesIO(path.read_bytes())) as image:
                require(image.format == "PNG", "camera source is not PNG")
                require(image.size == tuple(expected_dimensions[name]), "camera dimensions mismatch")
                image.load()
    return {
        "case_id": expected_case_id,
        "frame_count": expected_frames,
        "camera_frames_decoded": len(seen_paths),
        "source_manifest_sha256": receipt["camera_manifest_source"]["sha256"],
        "physical_visibility_confirmed": False,
        "legal_verdict": None,
    }
