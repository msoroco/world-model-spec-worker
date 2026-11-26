"""Saved-only school-warning measurement; never infer legal or physical success."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_school_warning import CAMERAS, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def derive(attempt):
    attempt = Path(attempt)
    seal_path = attempt / "captured-source-hashes.json"
    if not seal_path.is_file():
        raise ValueError("Missing sealed original school-warning source inventory")
    seal = json.loads(seal_path.read_text())
    if seal.get("source_kind") != "original_native_capture":
        raise ValueError("Original Native capture source kind differs")
    required = {"road.xodr", "native-rows.jsonl", "video_frames.jsonl",
                "original-school-lane-review.json"} | {name + ".mkv" for name in CAMERAS}
    if not required <= set(seal.get("sha256", {})):
        raise ValueError("Four original cameras or school source missing from seal")
    for name, expected in seal["sha256"].items():
        source = attempt / name
        if not source.is_file():
            raise ValueError("Missing required source: " + name)
        if sha(source) != expected:
            raise ValueError("Changed original source: " + name)
    review = json.loads((attempt / "original-school-lane-review.json").read_text())
    if review.get("school_pedestrian_lane_survey") is not True:
        raise ValueError("Original school lane survey missing")
    for field in ("school_lane_source", "child_identity_source", "warning_asset_source",
                  "municipal_jurisdiction_source"):
        copied = attempt / ("review-" + field)
        if not copied.is_file() or sha(copied) != review.get(field + "_sha256"):
            raise ValueError("Original reviewed source missing: " + field)
    native = _jsonl(attempt / "native-rows.jsonl")
    frames = _jsonl(attempt / "video_frames.jsonl")
    if len(native) != 600 or len(frames) != 600:
        raise ValueError("Original Native/video frame coverage incomplete")
    for index, (row, frame) in enumerate(zip(native, frames)):
        if (row.get("video_frame") != index or frame.get("video_frame") != index or
                row.get("native_frame") != frame.get("native_frame") or
                row.get("camera_native_frames") != frame.get("camera_native_frames") or
                abs(row.get("time_s", -1) + .05 - frame.get("time_s", -10)) > 1e-4):
            raise ValueError("Original Native/video time or camera join differs")
        if row.get("vehicle_actor_id") is None or row.get("warning_actor_id") is None or row.get("child_actor_id") is None:
            raise ValueError("Original school-warning participant missing")
    context = {"source_kind": "original_native_school_warning_readback",
        "native_map_sha256": sha(attempt / "road.xodr"),
        "school_lane_geometry_sha256": sha(attempt / "review-school_lane_source"),
        "vehicle_extent_sha256": sha(attempt / "native-rows.jsonl"),
        "warning_actor_sha256": sha(attempt / "review-warning_asset_source"),
        "warning_state_source_sha256": sha(attempt / "native-rows.jsonl"),
        "child_presence_source_sha256": sha(attempt / "review-child_identity_source"),
        "school_pedestrian_lane_survey": True,
        "nearest_lane_side_x_m": review["nearest_lane_side_x_m"],
        "vehicle_length_m": native[0]["vehicle_length_m"]}
    if any(abs(row["vehicle_length_m"] - context["vehicle_length_m"]) > 1e-3 for row in native):
        raise ValueError("Original vehicle body extent changed")
    measured = measure(context, native)
    measured["case_id"] = seal["case_id"]
    measured["original_source_inventory_sha256"] = sha(seal_path)
    measured["physical_completion"] = None
    return measured


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved result; use fresh output")
    measured = derive(attempt)
    construction = json.loads((attempt / "construction.json").read_text())
    case_id = construction["case_id"]
    if measured["case_id"] != case_id:
        raise ValueError("Saved exact school-warning case identity differs")
    from worker_exchange.native_output import write_result
    description = construction["recording_description"]
    write_result(attempt, {
        "case_id": case_id, "measured_values": measured,
        "target_checks": [{"target": "observed school-warning stop distance and release",
            "requested": True, "measured": True,
            "method": "sealed original 600-frame Native and four-camera source join",
            "tolerance": "requested 55/40-foot station is engineering target; legal reference point unresolved",
            "matched": False, "physical_cause_confirmed": False,
            "cause_evidence": {"source_inventory_sha256": measured["original_source_inventory_sha256"]}}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "accepted": False,
        "termination_reason": "Saved measurement only; physical and legal review pending",
        "physical_failure_flags": ["Original lane, child and warning pixels require independent review"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": [{"name": channel["name"], "unit": channel["unit"],
                                "reference": "native-rows.jsonl"}
                               for channel in description["channels"]],
        "realized_observables": {}})
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"school_warning_stop": {
                  "method": "derive", "value": measured,
                  "sources": {name: sha(attempt / name) for name in
                              ("road.xodr", "native-rows.jsonl", "video_frames.jsonl",
                               "original-school-lane-review.json")}}},
              "source_complete": True, "physical_or_legal_acceptance": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
