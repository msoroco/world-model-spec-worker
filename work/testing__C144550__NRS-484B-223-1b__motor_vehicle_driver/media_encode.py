"""Lossless original four-view and synchronized primary video encoding."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from camera_capture import SIZES


def encode(attempt: str | Path, *, run=subprocess.run) -> dict:
    attempt = Path(attempt)
    media = attempt / "original-camera-frames"
    rows = json.loads((media / "camera-manifest.json").read_text())
    if len(rows) != 900 or any(row.get("frame") != i or set(row.get("views", {})) != set(SIZES)
                                for i, row in enumerate(rows)):
        raise ValueError("four original joined views across 900 frames required")
    base = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    commands = {}
    for name in SIZES:
        commands[name] = [*base, "-framerate", "20", "-i",
                          str(media / (name + "-%06d.png")), "-frames:v", "900",
                          "-c:v", "ffv1", str(attempt / (name + ".mkv"))]
    commands["raw"] = [*base,
        *sum((["-i", str(attempt / (name + ".mkv"))] for name in SIZES), []),
        "-filter_complex", "[0:v]scale=960:540[a];[1:v]scale=960:540[b];"
        "[2:v]scale=960:540[c];[3:v]scale=960:540[d];"
        "[a][b][c][d]xstack=inputs=4:layout=0_0|960_0|0_540|960_540[v]",
        "-map", "[v]", "-frames:v", "900", "-c:v", "ffv1",
        str(attempt / "raw.mkv")]
    for name, command in commands.items():
        target = attempt / (name + ".mkv")
        if target.exists():
            raise ValueError("original video already exists: " + name)
        run(command, check=True)
        if not target.is_file() or target.stat().st_size == 0:
            raise ValueError("original video encoding failed: " + name)
    return {name: 0 for name in commands}
