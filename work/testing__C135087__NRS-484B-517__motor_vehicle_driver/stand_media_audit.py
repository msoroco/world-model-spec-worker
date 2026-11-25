"""Decode and count four original stand cameras without making a pixel claim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from stand import SourceError


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _run(args):
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode:
        raise SourceError("original video probe/decode failed: " + result.stderr.strip()[:300])
    return result.stdout


def audit(attempt, root, *, expected_frames=900, dimensions=None):
    """Require exact 20 Hz decode from all four hash-sealed original MKVs."""
    root = Path(root).resolve()
    if set(attempt.get("cameras", {})) != set(CAMERAS):
        raise SourceError("four original cameras required")
    if attempt.get("frame_count") != expected_frames or attempt.get("fps") != 20:
        raise SourceError("camera episode profile mismatch")
    streams = {}
    for name in CAMERAS:
        ref = attempt["cameras"][name]
        if ref.get("path") != name + ".mkv" or ref.get("fps") != 20 or ref.get("frame_count") != expected_frames:
            raise SourceError("camera source/profile mismatch")
        path = root / ref["path"]
        if path.is_symlink() or not path.is_file():
            raise SourceError("original camera missing or symlinked")
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
            raise SourceError("original camera hash mismatch")
        raw = _run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,r_frame_rate:frame=best_effort_timestamp_time",
                    "-show_frames", "-of", "json", str(path)])
        probe = json.loads(raw)
        video = probe.get("streams", [{}])[0]
        if video.get("r_frame_rate") != "20/1":
            raise SourceError("original camera rate differs from 20 Hz")
        if dimensions is not None and (video.get("width"), video.get("height")) != tuple(dimensions[name]):
            raise SourceError("original camera dimensions differ")
        times = [float(row["best_effort_timestamp_time"]) for row in probe.get("frames", [])]
        if len(times) != expected_frames or any(abs((time-times[0])-i/20) > .001
                                                for i, time in enumerate(times)):
            raise SourceError("original camera frame/time continuity failed")
        _run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"])
        streams[name] = {"sha256": ref["sha256"], "decoded_frames": len(times),
                         "first_pts_s": times[0], "last_pts_s": times[-1]}
    return {"format": "c135087-stand-media-audit-v1", "case_id": attempt["case_id"],
            "camera_streams": streams, "decoded_view_frames": expected_frames * 4,
            "diagnostic_fixture": expected_frames != 900,
            "physical_acceptance": False, "pixel_visibility": "unreviewed",
            "legal_judgment": None}
