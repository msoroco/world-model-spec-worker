"""Independently verify four original, frame-joined camera sources."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

from native_sight_cameras import SPECS


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(attempt: Path, expected_frames: int = 900) -> dict:
    attempt = Path(attempt).resolve()
    inventory = json.loads((attempt / "inventory.json").read_text())
    sources = inventory.get("camera_sources")
    if not isinstance(sources, dict) or set(sources) != {name for name, _, _ in SPECS}:
        raise ValueError("exact four original camera sources required")
    if type(expected_frames) is not int or expected_frames < 1:
        raise ValueError("positive expected frame count required")
    frame_source = inventory.get("sources", {}).get("frame_map")
    if not isinstance(frame_source, dict) or frame_source.get("path") != "frame_map.json":
        raise ValueError("sealed original frame map required")
    frame_path = (attempt / frame_source["path"]).resolve()
    if not frame_path.is_relative_to(attempt) or not frame_path.is_file():
        raise ValueError("original frame map missing")
    frame_hash = _sha(frame_path)
    if frame_hash != frame_source.get("sha256"):
        raise ValueError("original frame map hash changed")
    frames = json.loads(frame_path.read_text()).get("frames")
    if not isinstance(frames, list) or len(frames) != expected_frames:
        raise ValueError("original frame map count mismatch")
    for index, row in enumerate(frames):
        if (not isinstance(row, dict) or type(row.get("frame")) is not int or
                type(row.get("time_s")) not in (int, float) or
                not math.isfinite(row["time_s"])):
            raise ValueError("original frame map identity missing")
        if index and (row["frame"] != frames[index - 1]["frame"] + 1 or
                      not 0.045 <= row["time_s"] - frames[index - 1]["time_s"] <= 0.055):
            raise ValueError("original frame map is not contiguous at 20 Hz")
    output = {}
    for name, width, height in SPECS:
        entry = sources[name]
        if (not isinstance(entry, dict) or entry.get("path") != name + ".mkv" or
                entry.get("source_kind") != "original_native"):
            raise ValueError("original camera source binding missing: " + name)
        video = (attempt / entry["path"]).resolve()
        if not video.is_relative_to(attempt) or not video.is_file():
            raise ValueError("original camera video missing: " + name)
        digest = _sha(video)
        if digest != entry.get("sha256"):
            raise ValueError("original camera video hash changed: " + name)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=codec_name,nb_read_frames,r_frame_rate,width,height",
             "-of", "json", str(video)], capture_output=True, text=True, check=False)
        if probe.returncode:
            raise ValueError("original camera ffprobe failed: " + name)
        streams = json.loads(probe.stdout).get("streams", [])
        if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
                streams[0].get("nb_read_frames") != str(expected_frames) or
                streams[0].get("r_frame_rate") != "20/1" or
                streams[0].get("width") != width or streams[0].get("height") != height):
            raise ValueError("original camera capture profile failed: " + name)
        decoded = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(video),
             "-f", "null", "-"], capture_output=True, check=False)
        if decoded.returncode:
            raise ValueError("original camera full decode failed: " + name)
        output[name] = {"sha256": digest, "frames": expected_frames,
                        "width": width, "height": height, "fps": 20,
                        "full_decode_passed": True}
    return {"format": "c129731-native-four-view-audit-v1",
            "case_id": inventory.get("case_id"), "sources": output,
            "frame_map_sha256": frame_hash, "frame_count": expected_frames,
            "legal_visibility_judgment": "unresolved"}
