"""Encode retained original PNG views into lossless Native review videos."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from native_history import CAMERAS


def commands(media_root, attempt):
    media_root, attempt = Path(media_root), Path(attempt)
    base = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    result = {}
    for name in CAMERAS:
        result[name] = [*base, "-framerate", "20", "-i",
                        str(media_root / (name + "-%06d.png")), "-frames:v", "900",
                        "-c:v", "ffv1", str(attempt / (name + ".mkv"))]
    result["raw"] = [*base,
        "-i", str(attempt / "overview.mkv"),
        "-i", str(attempt / "approach.mkv"),
        "-i", str(attempt / "reference_corner.mkv"),
        "-i", str(attempt / "driver_reference.mkv"),
        "-filter_complex", "[0:v]scale=960:540[a];[1:v]scale=960:540[b];"
                           "[2:v]scale=960:540[c];[3:v]scale=960:540[d];"
                           "[a][b][c][d]xstack=inputs=4:layout=0_0|960_0|0_540|960_540[v]",
        "-map", "[v]", "-frames:v", "900", "-c:v", "ffv1",
        str(attempt / "raw.mkv")]
    return result


def encode(media_root, attempt, *, run=subprocess.run):
    media_root, attempt = Path(media_root), Path(attempt)
    manifest = json.loads((media_root / "camera-manifest.json").read_text())
    if len(manifest) != 900 or any(row.get("frame") != index for index, row in enumerate(manifest)):
        raise ValueError("900 original joined camera frames required before encoding")
    for row in manifest:
        if set(row.get("views", {})) != set(CAMERAS):
            raise ValueError("four original camera views required before encoding")
    for name, command in commands(media_root, attempt).items():
        target = attempt / (name + ".mkv")
        if target.exists():
            raise FileExistsError(target)
        run(command, check=True)
        if not target.is_file() or target.stat().st_size == 0:
            raise ValueError("lossless original camera encoder produced no video: " + name)
    return {name: 0 for name in (*CAMERAS, "raw")}
