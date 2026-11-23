"""Compose four synchronized original views into a review video.

This command reads saved source streams only. It emits a hash-bound receipt after
ffprobe confirms every input and the output have the frame-map frame count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

NAMES = ("overview", "approach", "reference_corner", "driver_reference")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_frames(path: Path) -> int:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-count_frames", "-show_entries", "stream=nb_read_frames",
               "-of", "default=nokey=1:noprint_wrappers=1", str(path)]
    value = subprocess.check_output(command, text=True).strip()
    if not value.isdecimal():
        raise ValueError("full frame count unavailable: " + str(path))
    return int(value)


def map_frames(path: Path) -> int:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows or any(row.get("video_frame") != index for index, row in enumerate(rows)):
        raise ValueError("frame map is empty or not consecutive")
    if any(not isinstance(row.get("carla_frame"), int) or
           not isinstance(row.get("time_s"), (float, int)) for row in rows):
        raise ValueError("frame map lacks original frame/time")
    return len(rows)


def compose(attempt: Path, *, output: Path | None = None,
            receipt: Path | None = None) -> dict:
    attempt = attempt.resolve()
    output = output or attempt / "raw.mkv"
    receipt = receipt or attempt / "four-view-composition.json"
    output = output.resolve()
    receipt = receipt.resolve()
    if output.parent != attempt or receipt.parent != attempt:
        raise ValueError("output and receipt must be in the saved attempt")
    if output.exists() or receipt.exists():
        raise ValueError("composition output or receipt already exists")
    mapping = attempt / "video_frames.jsonl"
    frames = map_frames(mapping)
    sources = [attempt / (name + ".mkv") for name in NAMES]
    for source in sources:
        if not source.is_file() or count_frames(source) != frames:
            raise ValueError("source video absent or frame count differs: " + str(source))
    # Preserve each view in a fixed quadrant without synthesizing replacement frames.
    filtergraph = ("[0:v]scale=960:540:flags=bicubic,setsar=1[a];"
                   "[1:v]scale=960:540:flags=bicubic,setsar=1[b];"
                   "[2:v]scale=960:540:flags=bicubic,setsar=1[c];"
                   "[3:v]scale=960:540:flags=bicubic,setsar=1[d];"
                   "[a][b][c][d]xstack=inputs=4:layout=0_0|960_0|0_540|960_540[v]")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n"]
    for source in sources:
        command.extend(["-i", str(source)])
    command.extend(["-filter_complex", filtergraph, "-map", "[v]", "-an",
                    "-c:v", "ffv1", "-pix_fmt", "bgr0", str(output)])
    try:
        subprocess.run(command, check=True)
        if count_frames(output) != frames:
            raise ValueError("composed output frame count differs from original map")
        result = {"format": "synchronized-four-view", "frames": frames,
                  "frame_map_sha256": digest(mapping),
                  "sources": {name: digest(source) for name, source in zip(NAMES, sources)},
                  "primary_sha256": digest(output),
                  "layout": {"overview": "upper_left", "approach": "upper_right",
                             "reference_corner": "lower_left",
                             "driver_reference": "lower_right"}}
        receipt.write_text(json.dumps(result, indent=2) + "\n")
        return result
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compose(args.attempt), sort_keys=True))


if __name__ == "__main__":
    main()
