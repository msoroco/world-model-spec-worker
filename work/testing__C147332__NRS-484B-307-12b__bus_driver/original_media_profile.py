"""Audit the exact saved camera encoding profile before pixel review."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def audit(attempt: Path) -> dict:
    attempt = Path(attempt)
    frame_map = attempt / "camera-frame-map.jsonl"
    if not frame_map.is_file():
        raise ValueError("original camera frame map missing")
    expected_frames = None
    if frame_map.is_file():
        rows = [json.loads(line) for line in frame_map.read_text().splitlines() if line.strip()]
        if not rows:
            raise ValueError("original camera frame map empty")
        first_frame = rows[0].get("frame")
        first_time = rows[0].get("elapsed_seconds")
        if (type(first_frame) is not int or type(first_time) not in (int, float) or
                not math.isfinite(first_time)):
            raise ValueError("original camera frame map lacks frame and time")
        for index, row in enumerate(rows):
            frame = row.get("frame")
            time = row.get("elapsed_seconds")
            if (type(frame) is not int or frame != first_frame + index or
                    type(time) not in (int, float) or not math.isfinite(time) or
                    abs(time - first_time - index / 20) > .001):
                raise ValueError("original camera frame map is not contiguous at 20 Hz")
            if row.get("camera_names") != list(CAMERAS):
                raise ValueError("original camera frame map has wrong camera identity")
        expected_frames = len(rows)
    results = {}
    for name in CAMERAS:
        path = attempt / (name + ".mkv")
        if not path.is_file():
            raise ValueError("original camera missing: " + name)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-count_frames",
             "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_read_frames",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=90)
        if probe.returncode:
            raise ValueError("original camera profile probe failed: " + name)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1:
            raise ValueError("original camera video stream count invalid: " + name)
        stream = streams[0]
        if stream.get("codec_type") != "video":
            raise ValueError("original camera stream is not video: " + name)
        width, height = (1920, 1080) if name == "overview" else (1280, 720)
        expected = {"codec_name": "ffv1", "width": width, "height": height,
                    "r_frame_rate": "20/1", "avg_frame_rate": "20/1"}
        if any(stream.get(key) != value for key, value in expected.items()):
            raise ValueError("original camera encoding profile differs: " + name)
        try:
            decoded_frames = int(stream["nb_read_frames"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("original camera decoded frame count missing: " + name) from exc
        if decoded_frames < 1 or (expected_frames is not None and decoded_frames != expected_frames):
            raise ValueError("original camera decoded frame count differs: " + name)
        results[name] = {**expected, "decoded_frames": decoded_frames}
    return {"format": "red-x-original-camera-profile", "cameras": results,
            "frame_map_count": expected_frames,
            "physical_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = audit(args.attempt)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print("four original camera profiles verified")


if __name__ == "__main__":
    main()
