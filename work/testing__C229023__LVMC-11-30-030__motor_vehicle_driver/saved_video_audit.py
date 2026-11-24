"""Decode all four saved Native videos and join them to original world ticks.

This is a source and media integrity check. It does not certify that the
pedestrian, lead vehicle, crosswalk or passing maneuver is physically visible.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from native_crosswalk_capture import CAMERAS, FRAME_COUNT
from saved_capture_audit import audit as audit_capture


DEFAULT_SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
                 "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path: Path) -> dict:
    run = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(run.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original video stream required: " + path.name)
    return streams[0]


def _decode(path: Path, width: int, height: int, expected_frames: int) -> dict:
    frame_bytes = width * height * 3
    process = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                                "-map", "0:v:0", "-an", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                "pipe:1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    first_digest = None
    distinct = False
    frames = 0
    try:
        while True:
            block = process.stdout.read(frame_bytes)
            if not block:
                break
            if len(block) != frame_bytes:
                raise ValueError("truncated decoded camera frame: " + path.name)
            frames += 1
            if frames > expected_frames:
                raise ValueError("extra decoded camera frame: " + path.name)
            frame_digest = hashlib.sha256(block).digest()
            if first_digest is None:
                first_digest = frame_digest
            elif frame_digest != first_digest:
                distinct = True
            digest.update(block)
        error = process.stderr.read().decode("utf-8", "replace")
        if process.wait() != 0:
            raise ValueError("camera decoder failed: " + path.name + ": " + error[-400:])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    if frames != expected_frames:
        raise ValueError("incomplete decoded camera: " + path.name)
    return {"frames": frames, "rgb_sha256": digest.hexdigest(),
            "varied_frames": distinct}


def audit(*, directory: str | Path, case_id: str,
          sizes: dict[str, tuple[int, int]] | None = None,
          expected_frames: int = FRAME_COUNT) -> dict:
    root = Path(directory)
    if sizes is None:
        sizes = DEFAULT_SIZES
    if set(sizes) != set(CAMERAS) or expected_frames < 2:
        raise ValueError("four exact camera views and at least two frames required")
    capture = audit_capture(directory=root, case_id=case_id)
    if capture["frame_count"] != expected_frames:
        raise ValueError("saved video and original frame map counts differ")
    videos = {}
    for name in CAMERAS:
        path = root / (name + ".mkv")
        if path.is_symlink() or not path.is_file():
            raise ValueError("original camera video missing: " + name)
        width, height = sizes[name]
        if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
            raise ValueError("positive exact camera dimensions required")
        stream = _probe(path)
        if (stream.get("codec_name") != "ffv1" or stream.get("width") != width
                or stream.get("height") != height or stream.get("avg_frame_rate") != "20/1"):
            raise ValueError("original camera encoding/profile differs: " + name)
        decoded = _decode(path, width, height, expected_frames)
        videos[name] = {"video_sha256": _file_sha256(path), **decoded}
    return {"case_id": case_id, "frame_map_sha256": capture["frame_map_sha256"],
            "first_native_frame": capture["first_native_frame"],
            "last_native_frame": capture["last_native_frame"], "videos": videos,
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}
