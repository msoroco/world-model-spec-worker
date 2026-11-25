"""Independent hash, frame-join and complete decode audit for Native cameras."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from native_capture import CAMERA_SPECS
from overpass_source import FRAMES, sha


def audit_media(attempt, *, expected_frames=FRAMES, specs=CAMERA_SPECS):
    root = Path(attempt).resolve()
    manifest = json.loads((root / "original-sources.json").read_text())
    if manifest.get("format") != "c188132-original-sources-v1":
        raise ValueError("original camera source manifest absent")

    def source(key):
        item = manifest.get(key)
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("missing original camera source: " + key)
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("missing or stale original camera source: " + key)
        return path

    frame_map = [json.loads(line) for line in source("frame_map").read_text().splitlines() if line]
    joins = [json.loads(line) for line in source("camera_joins").read_text().splitlines() if line]
    if len(frame_map) != expected_frames or len(joins) != expected_frames:
        raise ValueError("original camera frame count differs")
    if [(row["frame"], row["time_s"]) for row in frame_map] != [
            (row["frame"], row["time_s"]) for row in joins]:
        raise ValueError("original camera frame and world time join differs")
    for joined in joins:
        if set(joined.get("cameras", {})) != set(specs):
            raise ValueError("four original camera frame joins required")
        for name, (width, height) in specs.items():
            item = joined["cameras"][name]
            if (item.get("frame") != joined["frame"] or item.get("width") != width or
                    item.get("height") != height or item.get("bytes") != width * height * 4 or
                    item.get("pixel_format") != "bgra"):
                raise ValueError(name + " original camera frame join differs")

    decoded = {}
    for name, (width, height) in specs.items():
        path = source("video_" + name)
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                "-select_streams", "v:0", "-show_entries",
                                "stream=width,height,r_frame_rate,nb_read_frames",
                                "-of", "json", str(path)], capture_output=True, text=True)
        if probe.returncode:
            raise ValueError(name + " ffprobe failed: " + probe.stderr.strip())
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1 or any((int(streams[0]["width"]) != width,
                                     int(streams[0]["height"]) != height,
                                     streams[0]["r_frame_rate"] != "20/1",
                                     int(streams[0].get("nb_read_frames", -1)) != expected_frames)):
            raise ValueError(name + " original video dimensions, rate or frame count differ")
        decode = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                                 "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                                capture_output=True, text=True)
        if decode.returncode:
            raise ValueError(name + " complete original video decode failed: " + decode.stderr.strip())
        decoded[name] = {"sha256": sha(path), "frames": expected_frames,
                         "width": width, "height": height, "full_decode_passed": True}
    return {"format": "c188132-original-media-audit-v1", "case_id": joins[0]["case_id"],
            "frames": expected_frames, "cameras": decoded,
            "frame_map_sha256": sha(source("frame_map")),
            "camera_joins_sha256": sha(source("camera_joins")),
            "physical_visibility_claimed": False}
