"""Audit the exact saved camera encoding profile before pixel review."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def audit(attempt: Path) -> dict:
    attempt = Path(attempt)
    results = {}
    for name in CAMERAS:
        path = attempt / (name + ".mkv")
        if not path.is_file():
            raise ValueError("original camera missing: " + name)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,width,height,r_frame_rate,avg_frame_rate",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=90)
        if probe.returncode:
            raise ValueError("original camera profile probe failed: " + name)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1:
            raise ValueError("original camera video stream count invalid: " + name)
        stream = streams[0]
        width, height = (1920, 1080) if name == "overview" else (1280, 720)
        expected = {"codec_name": "ffv1", "width": width, "height": height,
                    "r_frame_rate": "20/1", "avg_frame_rate": "20/1"}
        if any(stream.get(key) != value for key, value in expected.items()):
            raise ValueError("original camera encoding profile differs: " + name)
        results[name] = expected
    return {"format": "red-x-original-camera-profile", "cameras": results,
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
