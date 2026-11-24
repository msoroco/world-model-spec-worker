"""Seal an acquired 20 Hz camera frame map and media for saved-source audit.

Call only after Native capture exits. The caller supplies original camera frame
readbacks and media files; this module never fabricates camera observations.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_audit import CAMERAS, CASE_PREFIX
from speed_boundary import EXPECTED_FRAMES, measure


def _bind(attempt: Path, path: Path) -> dict:
    if (not path.is_file() or path.is_symlink() or
            not path.resolve().is_relative_to(attempt.resolve())):
        raise ValueError("camera source missing or outside attempt")
    return {"path": str(path.relative_to(attempt)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def finalize_capture(attempt: Path, case_id: str, camera_frames: list[dict],
                     camera_media: dict[str, Path], *,
                     site_source: Path | None = None) -> dict:
    """Write source index once, only after all original sources pass joins."""
    attempt = Path(attempt)
    if case_id not in {CASE_PREFIX + suffix for suffix in ("below", "equal", "above")}:
        raise ValueError("unknown exact case")
    index_path, map_path = attempt / "capture-index.json", attempt / "frame-map.json"
    if index_path.exists() or map_path.exists():
        raise ValueError("capture finalization already exists")
    speed = measure(attempt, case_id)
    motion_path = attempt / "native-motion-receipt.json"
    motion = json.loads(motion_path.read_text(encoding="utf-8"))
    if (motion.get("case_id") != case_id or
            motion.get("native_run_id") != speed["native_run_id"] or
            motion.get("speed_source_sha256") != speed["source_sha256"] or
            motion.get("diagnostic_fixture") != speed["diagnostic_fixture"]):
        raise ValueError("Native motion and original speed differ")
    original_camera_hash = motion.get("camera_frame_readback_sha256")
    if original_camera_hash is not None:
        readback_path = attempt / "camera-frame-readback.json"
        readback_raw = readback_path.read_bytes()
        if hashlib.sha256(readback_raw).hexdigest() != original_camera_hash:
            raise ValueError("original camera readback hash differs")
        readback = json.loads(readback_raw)
        if (readback.get("case_id") != case_id or
                readback.get("native_run_id") != speed["native_run_id"] or
                readback.get("frames") != camera_frames):
            raise ValueError("original camera readback and finalization differ")
    if (not isinstance(camera_frames, list) or len(camera_frames) != EXPECTED_FRAMES or
            not isinstance(camera_media, dict) or set(camera_media) != set(CAMERAS)):
        raise ValueError("four camera sources and 900 original frames required")
    descriptor = json.loads((attempt / "speed-source.json").read_text(encoding="utf-8"))
    origin = descriptor["source_frame_origin"]
    for i, row in enumerate(camera_frames):
        if (not isinstance(row, dict) or row.get("frame") != origin + i or
                row.get("camera_frames") != {camera: origin + i for camera in CAMERAS}):
            raise ValueError("original camera frame join differs")
    bindings = {camera: _bind(attempt, Path(camera_media[camera])) for camera in CAMERAS}
    frame_map = {"case_id": case_id, "native_run_id": speed["native_run_id"],
                 "frames": camera_frames}
    raw = (json.dumps(frame_map, sort_keys=True, separators=(",", ":")) + "\n").encode()
    index = {"format": "c10301-capture-index-v1", "case_id": case_id,
             "frame_count": EXPECTED_FRAMES,
             "diagnostic_fixture": speed["diagnostic_fixture"],
             "native_motion": _bind(attempt, motion_path),
             "frame_map": {"path": map_path.name,
                           "sha256": hashlib.sha256(raw).hexdigest()},
             "cameras": bindings}
    if site_source is not None:
        source_binding = _bind(attempt, Path(site_source))
        site = json.loads(Path(site_source).read_text(encoding='utf-8'))
        if (site.get('case_id') != case_id or
                site.get('diagnostic_fixture') != speed['diagnostic_fixture'] or
                site.get('format') != 'c10301-native-site-v1'):
            raise ValueError('original Native site source differs')
        index['native_site'] = source_binding
    map_path.write_bytes(raw)
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    return index
