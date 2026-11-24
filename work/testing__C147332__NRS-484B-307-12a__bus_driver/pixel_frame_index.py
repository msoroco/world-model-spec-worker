"""Index every decoded original camera frame for later pixel visibility review.

This records pixel hashes and frame identities. It does not decide visibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from delivery_audit import CAMERAS, audit_attempt


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_exact(stream, length):
    chunks = []
    remaining = length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ValueError("original video truncated during pixel indexing")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def frame_hashes(video, *, width, height, expected):
    """Decode the full RGB stream, retaining only one frame in memory."""
    command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-f", "rawvideo",
               "-pix_fmt", "rgb24", "pipe:1"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    hashes = []
    frame_bytes = width * height * 3
    try:
        for _ in range(expected):
            hashes.append(hashlib.sha256(read_exact(process.stdout, frame_bytes)).hexdigest())
        if process.stdout.read(1):
            raise ValueError("original video contains an unindexed extra frame")
        error = process.stderr.read()
        if process.wait(timeout=120) or error.strip():
            raise ValueError("original video pixel decode failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    return hashes


def index_attempt(attempt, *, diagnostic=False):
    attempt = Path(attempt).resolve()
    audit = audit_attempt(attempt, diagnostic=diagnostic)
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()
               if line.strip()]
    count = len(mapping)
    if not count or any(row.get("video_frame") != i for i, row in enumerate(mapping)):
        raise ValueError("original video frame index differs")
    cameras = {}
    for name in CAMERAS:
        video = attempt / (name + ".mkv")
        if video.is_symlink() or video.resolve().parent != attempt:
            raise ValueError("original camera source escapes attempt")
        width, height = SIZES[name]
        hashes = frame_hashes(video, width=width, height=height, expected=count)
        cameras[name] = {"video_sha256": sha(video), "width": width, "height": height,
                         "frames": [{"video_frame": i, "carla_frame": mapping[i]["carla_frame"],
                                     "time_s": mapping[i]["time_s"], "rgb24_sha256": value}
                                    for i, value in enumerate(hashes)]}
    return {"format": "worker-original-pixel-frame-index", "case_id": json.loads(
                (attempt / "scene.json").read_text())["case_id"],
            "video_frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            "capture_seal_sha256": sha(attempt / "capture-seal.json"),
            "decoded_original_frames": count, "cameras": cameras,
            "diagnostic_fixture": diagnostic, "pixel_visibility_reviewed": False,
            "physical_acceptance_claimed": False,
            "scope": "Decoded pixel-byte custody and original frame join; no visibility inference"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    scratch = (REPO / ".runtime-work").resolve()
    output = Path(args.output).resolve()
    if not output.is_relative_to(scratch):
        raise ValueError("pixel index output must be under .runtime-work")
    if output.exists():
        raise ValueError("pixel index output must be fresh")
    report = index_attempt(args.attempt, diagnostic=args.diagnostic)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(report["case_id"], report["decoded_original_frames"],
          "all four original pixel streams indexed; visibility unreviewed")


if __name__ == "__main__":
    main()
