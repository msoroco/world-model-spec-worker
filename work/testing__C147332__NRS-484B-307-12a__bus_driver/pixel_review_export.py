"""Export source-bound original frames for human signal and bus review.

This creates viewable PPM images and a custody sheet. It never decides whether
the bus, signal, or lane association is visible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from pixel_frame_index import CAMERAS, REPO, SIZES, index_attempt, read_exact, sha


def selected_frames(count):
    if count < 3:
        raise ValueError("at least three original frames required for review export")
    return sorted({0, count // 2, count - 1})


def export(attempt, index_path, output, *, diagnostic=False):
    attempt, index_path, output = Path(attempt).resolve(), Path(index_path).resolve(), Path(output).resolve()
    scratch = (REPO / ".runtime-work").resolve()
    if not index_path.is_relative_to(scratch) or not output.is_relative_to(scratch):
        raise ValueError("pixel review inputs and output must remain under .runtime-work")
    if output.exists():
        raise ValueError("pixel review export output must be fresh")
    index = json.loads(index_path.read_text())
    actual = index_attempt(attempt, diagnostic=diagnostic)
    if index != actual:
        raise ValueError("pixel index differs from sealed original sources")
    frames = selected_frames(actual["decoded_original_frames"])
    output.mkdir(parents=True)
    samples = []
    for camera in CAMERAS:
        width, height = SIZES[camera]
        frame_size = width * height * 3
        command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(attempt / (camera + ".mkv")),
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for number, row in enumerate(index["cameras"][camera]["frames"]):
                pixels = read_exact(process.stdout, frame_size)
                pixel_hash = hashlib.sha256(pixels).hexdigest()
                if pixel_hash != row["rgb24_sha256"]:
                    raise ValueError("reviewed original frame pixel hash differs")
                if number in frames:
                    name = f"{camera}-frame-{number:06d}.ppm"
                    image = output / name
                    image.write_bytes(f"P6\n{width} {height}\n255\n".encode() + pixels)
                    samples.append({"camera": camera, "video_frame": number,
                                    "carla_frame": row["carla_frame"], "time_s": row["time_s"],
                                    "rgb24_sha256": pixel_hash, "image": name,
                                    "image_sha256": sha(image)})
            if process.stdout.read(1):
                raise ValueError("original video has an unindexed frame")
            error = process.stderr.read()
            if process.wait(timeout=120) or error.strip():
                raise ValueError("original video review export decode failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()
    sheet = {"format": "worker-original-pixel-review-export",
             "case_id": actual["case_id"], "pixel_index_sha256": sha(index_path),
             "capture_seal_sha256": actual["capture_seal_sha256"],
             "selected_video_frames": frames, "samples": samples,
             "review_questions": ["Is the original bus body visible in each selected view?",
                                  "Is the downward green arrow visibly legible and bus-facing?",
                                  "Does the displayed arrow align with the measured bus lane?"],
             "diagnostic_fixture": diagnostic, "pixel_visibility_reviewed": False,
             "physical_acceptance_claimed": False}
    (output / "review-sheet.json").write_text(json.dumps(sheet, indent=2) + "\n")
    return sheet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--pixel-index", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    sheet = export(args.attempt, args.pixel_index, args.output, diagnostic=args.diagnostic)
    print(sheet["case_id"], len(sheet["samples"]), "source-bound review images; visibility unreviewed")


if __name__ == "__main__":
    main()
