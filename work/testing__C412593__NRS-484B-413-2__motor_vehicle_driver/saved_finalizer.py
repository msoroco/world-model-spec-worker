"""Finalize one saved right-turn attempt from retained original sources."""

import hashlib
import json
import subprocess
from pathlib import Path

from native_sources import CAMERAS, RATE_HZ
from turn_signal_measurements import analyze


def _probe(path):
    process = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_read_frames",
         "-of", "json", str(path)], capture_output=True, text=True)
    if process.returncode:
        raise ValueError("Original camera decode failed: " + path.name)
    streams = json.loads(process.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("Single original camera stream required: " + path.name)
    return streams[0]


def finalize(root):
    root = Path(root)
    result = analyze(root)
    frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()
              if line.strip()]
    if len(frames) < 3 or any(row["video_frame"] != index for index, row in enumerate(frames)):
        raise ValueError("Incomplete original video frame map")
    streams = {}
    for camera in CAMERAS:
        path = root / (camera + ".mkv")
        if not path.is_file():
            raise ValueError("Missing original camera source: " + camera)
        metadata = _probe(path)
        if (metadata.get("codec_name") != "ffv1" or
                metadata.get("r_frame_rate") != str(RATE_HZ) + "/1" or
                int(metadata.get("nb_read_frames", -1)) != len(frames) or
                int(metadata.get("width", 0)) <= 0 or int(metadata.get("height", 0)) <= 0):
            raise ValueError("Original camera source profile/frame count differs: " + camera)
        streams[camera] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "codec": "ffv1", "width": metadata["width"],
                           "height": metadata["height"], "frames": len(frames)}
    return {"format": "c412593-saved-original-sources-v1", "measurement": result,
            "original_cameras": streams, "frames": len(frames),
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}
