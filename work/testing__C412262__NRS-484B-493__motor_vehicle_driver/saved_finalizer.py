"""Finalize source-sealed original traces without inferring statutory judgments."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from one_way_side_observations import observe
from street_scene_construction import ASSIGNMENT, load_case

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_video(path: Path, view: str) -> None:
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
            data.get("nb_read_frames") != "900"):
        raise ValueError("original camera decode/profile mismatch: " + view)


def finalize(case_id: str, context: Path, trace: Path, receipt: Path,
             camera_manifest: Path) -> dict:
    case = load_case(case_id)
    measurement = observe(case_id, context, trace, receipt)
    original = json.loads(receipt.read_text())
    cameras = json.loads(camera_manifest.read_text())
    if cameras.get("assignment_id") != ASSIGNMENT or cameras.get("case_id") != case_id:
        raise ValueError("original camera manifest identity mismatch")
    if original.get("camera_manifest_sha256") != sha(camera_manifest):
        raise ValueError("original camera manifest seal mismatch")
    if original.get("frame_count") != 900 or len(measurement["samples"]) != 900:
        raise ValueError("full original 45 s, 20 Hz trace required")
    if cameras.get("fps") != 20 or cameras.get("frame_count") != 900:
        raise ValueError("original four-camera cadence mismatch")
    streams = cameras.get("streams")
    if not isinstance(streams, dict) or set(streams) != set(VIEWS):
        raise ValueError("four original camera streams required")
    for view in VIEWS:
        stream = streams[view]
        path = camera_manifest.parent / stream.get("path", "")
        if (not path.is_file() or path.is_symlink() or
                stream.get("sha256") != sha(path) or
                stream.get("frame_count") != 900 or stream.get("fps") != 20):
            raise ValueError("source-sealed original camera stream missing: " + view)
        inspect_video(path, view)
    source_context = json.loads(context.read_text())
    for key, expected in (("street_direction_request", case["street_direction_request"]),
                          ("vehicle_side_request", case["vehicle_side_request"]),
                          ("activity_request", case["activity_request"]),
                          ("notice_request", case["notice_request"])):
        if source_context.get(key) != expected:
            raise ValueError("original context differs from exact intervention: " + key)
    measurement["camera_manifest_sha256"] = sha(camera_manifest)
    measurement["camera_stream_sha256"] = {view: streams[view]["sha256"] for view in VIEWS}
    measurement["original_protocol_checked"] = True
    measurement["statutory_disposition"] = "unresolved_pending_source_review"
    return measurement


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("case", "context", "trace", "receipt", "camera-manifest", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = finalize(args.case, Path(args.context), Path(args.trace),
                      Path(args.receipt), Path(args.camera_manifest))
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
