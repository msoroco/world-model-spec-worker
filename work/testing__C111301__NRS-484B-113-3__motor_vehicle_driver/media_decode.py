"""Full saved-camera decode for original backing attempts.

This checks software decodability and pixel source identity only. It cannot
establish that a pedestrian or the backing corridor is actually visible.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_backing import CAMERAS, _sealed, process

PRODUCTION_DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
                         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _probe(video):
    output = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", str(video),
    ], text=True, timeout=120)
    streams = json.loads(output).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original video stream required")
    return streams[0]


def audit_media(attempt, receipt, *, expected_frames=900, dimensions=None):
    """Decode every frame of each sealed camera file into frame checksums."""
    root = Path(attempt).resolve()
    media = receipt.get("media")
    if not isinstance(media, dict) or set(media) != set(CAMERAS):
        raise ValueError("four original camera videos required")
    expected_dimensions = dimensions or PRODUCTION_DIMENSIONS
    if set(expected_dimensions) != set(CAMERAS):
        raise ValueError("camera dimension plan incomplete")
    result = {}
    for name in CAMERAS:
        video = _sealed(root, media[name])
        before = hashlib.sha256(video.read_bytes()).hexdigest()
        stream = _probe(video)
        if stream.get("r_frame_rate") != "20/1":
            raise ValueError("original camera rate differs: " + name)
        size = [stream.get("width"), stream.get("height")]
        if expected_dimensions[name] is not None and size != list(expected_dimensions[name]):
            raise ValueError("original camera dimensions differ: " + name)
        decoded = subprocess.run([
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(video),
            "-vsync", "0", "-f", "framemd5", "-",
        ], capture_output=True, text=True, timeout=3600)
        if decoded.returncode:
            raise ValueError("original camera full decode failed: " + name)
        frame_lines = [line for line in decoded.stdout.splitlines() if line and not line.startswith("#")]
        if len(frame_lines) != expected_frames:
            raise ValueError("original camera decoded frame count differs: " + name)
        if hashlib.sha256(video.read_bytes()).hexdigest() != before:
            raise ValueError("original camera source changed during decode: " + name)
        result[name] = {"source_sha256": before, "decoded_frames": len(frame_lines),
                        "dimensions": size,
                        "frame_checksum_sha256": hashlib.sha256(
                            ("\n".join(frame_lines) + "\n").encode()).hexdigest()}
    return {"format": "saved-backing-four-camera-decode-v1", "cameras": result,
            "frame_count": expected_frames, "actual_pixels_decoded": True,
            "physical_visibility_confirmed": False, "legal_judgment": "unresolved"}


def process_delivery(attempt, expected_case, *, dimensions=None):
    measurement = process(attempt, expected_case)
    receipt = json.loads((Path(attempt) / "acquisition.json").read_text(encoding="utf-8"))
    measurement["media_decode"] = audit_media(attempt, receipt, dimensions=dimensions)
    measurement["full_video_decode"] = True
    measurement["actual_pixels"] = True
    return measurement


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = process_delivery(args.attempt, args.case)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
