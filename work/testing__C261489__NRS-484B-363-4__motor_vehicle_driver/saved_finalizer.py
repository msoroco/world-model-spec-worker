"""Independently remeasure sealed original school pass sources in saved processing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from school_pass import ASSIGNMENT, measure_original, validate_scene


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def inspect_video(path: Path, view: str, frames: int) -> None:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
         "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original video stream required: " + view)
    data = streams[0]
    if (data.get("codec_name") != "ffv1" or
            (data.get("width"), data.get("height")) != SIZES[view] or
            data.get("avg_frame_rate") not in ("20/1", "20") or
            data.get("nb_read_frames") != str(frames)):
        raise ValueError("original camera decode/profile mismatch: " + view)


def finalize(case_id: str, context: Path, trace: Path, receipt: Path,
             camera_manifest: Path) -> dict:
    root = context.parent
    for name, path in (("context.json", context), ("original-trace.jsonl", trace),
                       ("receipt.json", receipt), ("cameras.json", camera_manifest)):
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing required source: " + name)
    sealed = json.loads(receipt.read_text())
    scene = json.loads(context.read_text())
    if (sealed.get("assignment_id") != ASSIGNMENT or
            sealed.get("case_id") != case_id or
            sealed.get("source_kind") != "original_native_capture" or
            sealed.get("context_sha256") != sha(context) or
            sealed.get("trace_sha256") != sha(trace) or
            sealed.get("camera_manifest_sha256") != sha(camera_manifest)):
        raise ValueError("original school-pass source seal mismatch")
    validate_scene(scene, case_id)
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    if sealed.get("frame_count") != 900 or len(rows) != 900 or sealed.get("fps") != 20:
        raise ValueError("full original 45 s, 20 Hz trace required")
    measured = measure_original(rows, scene, case_id)
    cameras = json.loads(camera_manifest.read_text())
    if (cameras.get("assignment_id") != ASSIGNMENT or cameras.get("case_id") != case_id or
            cameras.get("frame_count") != 900 or cameras.get("fps") != 20 or
            set(cameras.get("streams", {})) != set(VIEWS)):
        raise ValueError("original four-camera identity/cadence differs")
    for view in VIEWS:
        stream = cameras["streams"][view]
        path = required(root, stream.get("path", ""))
        if stream.get("path") != view + ".mkv" or stream.get("sha256") != sha(path):
            raise ValueError("source-sealed original camera changed: " + view)
        inspect_video(path, view, 900)
    measured["camera_manifest_sha256"] = sha(camera_manifest)
    measured["camera_stream_sha256"] = {view: cameras["streams"][view]["sha256"] for view in VIEWS}
    measured["original_protocol_checked"] = True
    measured["statutory_disposition"] = "unresolved_pending_original_review"
    return measured
