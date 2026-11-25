"""Recorded-only lossless encoding of four original 20 Hz camera sources."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from freight_contract import SourceError
from saved_delivery import CAMERAS, probe_and_decode


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceError(reason)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode_cameras(attempt: Path, *, run_encoder=None, media_probe=None) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    run_encoder = run_encoder or subprocess.run
    media_probe = media_probe or probe_and_decode
    frame_map = [json.loads(line) for line in
                 (attempt / "frame-map.jsonl").read_text(encoding="utf-8").splitlines()]
    require(len(frame_map) == 900, "900 original camera frames required")
    for index, row in enumerate(frame_map):
        require(row.get("video_frame") == index and isinstance(row.get("native_frame"), int),
                "invalid original camera frame map")
    media = {}
    for name, size in CAMERAS.items():
        index_path = attempt / (name + "-camera.jsonl")
        require(index_path.is_file(), f"missing original camera index: {name}")
        rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
        require(len(rows) == 900, f"incomplete original camera: {name}")
        for index, row in enumerate(rows):
            expected = f"cameras/{name}/{index:06d}.png"
            require(row.get("original_frame") == index and
                    row.get("native_frame") == frame_map[index]["native_frame"] and
                    row.get("path") == expected,
                    f"original camera frame join mismatch: {name}")
            path = (attempt / expected).resolve(strict=True)
            require(path.is_relative_to(attempt) and path.is_file(),
                    f"original camera pixels escape attempt: {name}")
            pixels = path.read_bytes()
            require(hashlib.sha256(pixels).hexdigest() == row.get("sha256") and
                    pixels.startswith(b"\x89PNG\r\n\x1a\n"),
                    f"stale original camera pixels: {name}")
        output = attempt / (name + ".mkv")
        require(not output.exists(), f"retained original camera video exists: {name}")
        command = ["ffmpeg", "-nostdin", "-v", "error", "-framerate", "20",
                   "-i", str(attempt / "cameras" / name / "%06d.png"),
                   "-c:v", "ffv1", "-level", "3", "-n", str(output)]
        result = run_encoder(command, capture_output=True, text=True)
        require(result.returncode == 0 and output.is_file(), f"lossless camera encode failed: {name}")
        info = media_probe(output)
        require((info.get("width"), info.get("height")) == size and
                info.get("r_frame_rate") == "20/1" and
                str(info.get("nb_read_frames")) == "900",
                f"original encoded camera profile mismatch: {name}")
        media[name] = {"path": output.name, "sha256": sha256(output)}
    return media
