"""Independently check saved exact-case sources and four encoded camera views."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from capture_roundabout import CAMERAS, CAMERA_DIMENSIONS
from roundabout_delivery_audit import audit_delivery
from roundabout_measurements import ASSIGNMENT_ID, SUFFIXES, measure


def _required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(root, name):
    return [json.loads(line) for line in _required(root, name).read_text().splitlines()]


def _decode(path, expected, frames):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries",
        "stream=width,height,nb_read_frames,avg_frame_rate", "-of", "json",
        str(path)], check=True, capture_output=True, text=True, timeout=180)
    streams = json.loads(probe.stdout)["streams"]
    if len(streams) != 1:
        raise ValueError("camera stream count differs: " + path.name)
    stream = streams[0]
    if (stream["width"], stream["height"]) != tuple(expected) or (
            stream.get("avg_frame_rate") != "20/1" or
            int(stream["nb_read_frames"]) != frames):
        raise ValueError("camera frame profile differs: " + path.name)
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-f", "null", "-"], check=True,
        capture_output=True, timeout=180)
    return _sha(path)


def inspect(attempt, case_id, *, diagnostic):
    attempt = Path(attempt).resolve()
    if case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact selected case")
    map_path = _required(attempt, "original-map.json")
    trace_path = _required(attempt, "original-trace.jsonl")
    receipt_path = _required(attempt, "original-receipt.json")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("case_id") != case_id or bool(receipt.get("diagnostic_fixture")) != diagnostic:
        raise ValueError("exact source case or provenance differs")
    if not diagnostic:
        return audit_delivery(case_id=case_id, map_path=map_path,
                              trace_path=trace_path, receipt_path=receipt_path)
    provenance = json.loads(_required(attempt, "fixture-provenance.json").read_text())
    if provenance.get("case_id") != case_id or "CPU diagnostic only" not in provenance.get("scope", ""):
        raise ValueError("explicit CPU diagnostic provenance required")
    motion = measure(case_id=case_id, map_path=map_path,
                     trace_path=trace_path, receipt_path=receipt_path,
                     allow_diagnostic=True)
    original, graph, frame_map = (_rows(attempt, name) for name in
        ("original-trace.jsonl", "trace.jsonl", "video_frames.jsonl"))
    if len(original) != receipt.get("frame_count") or len(original) != len(graph) or (
            len(original) != len(frame_map)):
        raise ValueError("diagnostic original frame count differs")
    for index, (observed, body, mapped) in enumerate(zip(original, graph, frame_map)):
        if (mapped.get("video_frame") != index or
                mapped.get("carla_frame") != observed["frame"] or
                mapped.get("native_frame") != observed["frame"] or
                body.get("frame") != observed["frame"] or
                abs(mapped.get("time_s", -1) - observed["time_s"]) > 1e-4):
            raise ValueError("diagnostic frame/time/body join differs")
    hashes = {name: _decode(_required(attempt, name + ".mkv"),
        CAMERA_DIMENSIONS[name], len(original)) for name in CAMERAS}
    return {"format": "worker-independent-cpu-roundabout-delivery",
        "case_id": case_id, "diagnostic_fixture": True,
        "map_sha256": _sha(map_path), "trace_sha256": _sha(trace_path),
        "receipt_sha256": _sha(receipt_path), "camera_source_sha256": hashes,
        "frame_count": len(original), "full_encoded_camera_decodes": 4,
        "observed_entry_frame": motion["first_observed_ego_entry_frame"],
        "opponent_lane_id": motion["opponent_circulating_lane_id"],
        "physical_acceptance": False, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = inspect(args.attempt, args.case_id, diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": args.case_id, "diagnostic_fixture": args.diagnostic,
                      "frame_count": result["frame_count"],
                      "physical_acceptance": False}))


if __name__ == "__main__":
    main()
