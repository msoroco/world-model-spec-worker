"""Finalize sealed original nearest-view stop observations without a legal verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from stop_view_measurement import inspect_original
from stop_physical_completion import assess
from stop_sign_branch import ASSIGNMENT, CASES

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_video(path, view):
    process = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
         "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(process.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original video stream required: " + view)
    data = streams[0]
    if (data.get("codec_name") != "ffv1" or
            (data.get("width"), data.get("height")) != SIZES[view] or
            data.get("avg_frame_rate") not in ("20/1", "20") or
            data.get("nb_read_frames") != "900"):
        raise ValueError("original camera decode/profile mismatch: " + view)


def finalize(case_id, root):
    root = Path(root)
    context, trace, receipt_path, camera_path, packet_path = (
        root / name for name in ("context.json", "original-trace.jsonl", "receipt.json",
                                 "cameras.json", "comparison-packet.json"))
    receipt = json.loads(receipt_path.read_text())
    site = json.loads(context.read_text())
    cameras = json.loads(camera_path.read_text())
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    packet = json.loads(packet_path.read_text())
    if (receipt.get("assignment_id") != ASSIGNMENT or receipt.get("case_id") != case_id or
            receipt.get("source_kind") != "original_native_capture" or
            receipt.get("diagnostic_fixture") is not False or
            receipt.get("context_sha256") != sha(context) or
            receipt.get("trace_sha256") != sha(trace) or
            receipt.get("camera_manifest_sha256") != sha(camera_path) or
            cameras.get("assignment_id") != ASSIGNMENT or cameras.get("case_id") != case_id or
            site.get("site_sha256") != receipt.get("site_sha256") or
            packet.get("assignment_id") != ASSIGNMENT or
            packet.get("site") != site or packet.get("frames") != rows):
        raise ValueError("original stop source seal mismatch")
    site_path = root / "reviewed-site.json"
    source_index_path = root / "reviewed-sources.json"
    if (receipt.get("site_sha256") != sha(site_path) or
            receipt.get("reviewed_source_index_sha256") != sha(source_index_path)):
        raise ValueError("reviewed original stop site custody differs")
    reviewed = json.loads(site_path.read_text())
    source_index = json.loads(source_index_path.read_text())
    keys = ("map_source_sha256", "ego_route_source_sha256", "stop_sign_survey_sha256", "marking_survey_sha256",
            "view_ray_survey_sha256", "through_highway_survey_sha256")
    if set(source_index) != set(keys):
        raise ValueError("reviewed original stop source index incomplete")
    for key in keys:
        record = source_index[key]
        if (record.get("path") != "reviewed-" + key + ".source" or
                record.get("sha256") != sha(root / record["path"]) or
                record["sha256"] != reviewed.get(key) or
                record["sha256"] != site.get(key)):
            raise ValueError("reviewed original stop source byte seal differs: " + key)
    if (len(rows) != 900 or receipt.get("frame_count") != 900 or
            receipt.get("fps") != 20 or cameras.get("frame_count") != 900 or
            cameras.get("fps") != 20):
        raise ValueError("full original 45 s, 20 Hz trace required")
    streams = cameras.get("streams")
    if not isinstance(streams, dict) or set(streams) != set(VIEWS):
        raise ValueError("four original camera streams required")
    for view in VIEWS:
        item = streams[view]
        path = root / item.get("path", "")
        if (not path.is_file() or path.is_symlink() or
                item.get("sha256") != sha(path) or
                item.get("frame_count") != 900 or item.get("fps") != 20):
            raise ValueError("source-sealed original camera missing: " + view)
        inspect_video(path, view)
    measured = inspect_original(packet_path, case_id)
    measured["physical_completion_probe"] = assess(rows, site)
    measured["camera_manifest_sha256"] = sha(camera_path)
    measured["camera_stream_sha256"] = {view: streams[view]["sha256"] for view in VIEWS}
    measured["legal_hazard_judgment"] = None
    measured["physical_acceptance_claimed"] = False
    return measured


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(finalize(args.case, args.attempt),
                                      sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
