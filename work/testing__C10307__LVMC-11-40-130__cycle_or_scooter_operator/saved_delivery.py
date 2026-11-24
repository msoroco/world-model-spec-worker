"""Independent saved-only audit of C10307 original motion and four-camera media.

This checks acquisition integrity. It cannot prove bicycle/rack visibility or
decide whether the measured speed was reasonable and prudent.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from speed_measurement import measure


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _source(root: Path, entry: dict) -> Path:
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("media source escapes saved acquisition")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("missing original camera source")
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError("original camera source hash mismatch")
    return path


def _probe_and_decode(path: Path, expected_frames: int) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
         "-of", "json", str(path)], capture_output=True, text=True, check=True,
    )
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("camera video stream missing or ambiguous")
    stream = streams[0]
    if (stream.get("codec_name") != "ffv1" or
            stream.get("avg_frame_rate") != "20/1" or
            int(stream.get("nb_read_frames", -1)) != expected_frames):
        raise ValueError("original camera codec, rate or frame count mismatch")
    width, height = int(stream["width"]), int(stream["height"])
    if width <= 0 or height <= 0:
        raise ValueError("invalid original camera dimensions")
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0",
         "-f", "null", "-"], capture_output=True, text=True,
    )
    if decode.returncode:
        raise ValueError("original camera full decode failed: " + decode.stderr[-500:])
    return {"codec": "ffv1", "fps": 20, "frames": expected_frames,
            "width": width, "height": height}


def audit_saved(root: Path, case_id: str, *, minimum_frames: int = 900) -> dict:
    """Reject truncated, rebound or diagnostic episodes before saved processing."""
    root = Path(root)
    inventory = json.loads((root / "inventory.json").read_text())
    measured = measure(root, inventory, case_id)
    samples = measured["samples"]
    if len(samples) < minimum_frames or minimum_frames < 2:
        raise ValueError("original episode shorter than required 20 Hz window")
    capture = json.loads((root / "camera-manifest.json").read_text())
    if (capture.get("case_id") != case_id or
            capture.get("source_kind") != "original_live_native" or
            capture.get("diagnostic_fixture") is not False):
        raise ValueError("camera manifest is not an original case acquisition")
    if capture.get("frame_map_sha256") != inventory["sources"]["frame_map"]["sha256"]:
        raise ValueError("camera frame map differs from original motion")
    cameras = capture.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("four original camera sources required")
    expected = [row["frame"] for row in samples]
    if expected != list(range(expected[0], expected[0] + len(expected))):
        raise ValueError("original frame map is not consecutive")
    if any(abs(right["time_s"] - left["time_s"] - .05) > .005
           for left, right in zip(samples, samples[1:])):
        raise ValueError("original episode clock differs from 20 Hz")
    details = {}
    paths = set()
    for camera in CAMERAS:
        entry = cameras[camera]
        if entry.get("frame_ids") != expected:
            raise ValueError("camera callback frame join incomplete: " + camera)
        path = _source(root, entry)
        if path in paths:
            raise ValueError("camera sources are not distinct")
        paths.add(path)
        details[camera] = _probe_and_decode(path, len(expected))
        details[camera]["sha256"] = entry["sha256"]
    return {"format": "c10307-saved-delivery-audit-v1", "case_id": case_id,
            "source_kind": "original_live_native", "frame_count": len(expected),
            "original_frame_map_sha256": capture["frame_map_sha256"],
            "cameras": details, "legal_prudence": "unresolved",
            "physical_visibility_reviewed": False}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit_saved(args.root, args.case)
    if args.output.exists():
        raise ValueError("refusing to overwrite saved delivery audit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
