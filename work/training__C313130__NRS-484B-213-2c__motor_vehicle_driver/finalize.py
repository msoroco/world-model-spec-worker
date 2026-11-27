"""Saved-only tunnel approach measurement from immutable Native sources."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_tunnel import measure
from worker_exchange.native_output import physical_result, write_result


SOURCE_FILES = (
    "road.xodr", "portal-geometry.json", "road-direction-survey.json",
    "centreline-geometry.json", "vehicle-extents.jsonl", "sight-rays.jsonl",
    "tunnel-rows.jsonl", "trace.jsonl", "video_frames.jsonl",
    "capture/evidence.jsonl",
)
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHANNELS = (
    "st.elevated_structure", "drv.approaching", "rel.centre_distance",
    "st.sight_distance", "drv.sight_distance_adequate", "st.centre_line",
    "rel.occupies", "st.one_way_roadway",
)


def required(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_tunnel_approach(observation):
    return {key: observation[key] for key in (
        "within_100_ft_driving_frames", "left_of_centre_within_zone_frames",
        "blocked_sight_within_zone_frames", "left_and_blocked_within_zone_frames",
        "one_way_highway_surveyed", "sight_brackets_in_zone")}


def finalize(attempt, output):
    root, destination = Path(attempt).resolve(), Path(output)
    if destination.exists():
        raise ValueError("Retain prior selected measurement")
    config = json.loads(required(root, "config.json").read_text())
    context = json.loads(required(root, "tunnel-context.json").read_text())
    if context.get("case_id") != config["selected_case_id"]:
        raise ValueError("Selected tunnel case differs from source context")
    provenance = json.loads(required(root, "acquisition-provenance.json").read_text())
    diagnostic = provenance.get("provenance_kind") == "synthetic_fixture"
    if provenance.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("Tunnel source provenance differs")
    files = context.get("source_files", {})
    if set(files) != set(SOURCE_FILES):
        raise ValueError("Original tunnel source inventory incomplete")
    for name in SOURCE_FILES:
        if sha(required(root, name)) != context.get("source_sha256", {}).get(name):
            raise ValueError("Original tunnel source hash differs: " + name)
    for name in CAMERAS:
        required(root, name + ".mkv")
    source_rows = rows(required(root, "tunnel-rows.jsonl"))
    frame_map = rows(required(root, "video_frames.jsonl"))
    trace = rows(required(root, "trace.jsonl"))
    if len(source_rows) != len(frame_map) or len(trace) != 600:
        raise ValueError("Original tunnel source/frame count differs")
    for row, mapping, pose in zip(source_rows, frame_map, trace):
        if (row["native_frame"] != mapping["native_frame"] or
                row["native_frame"] != pose["frame"] or
                abs(row["time_s"] - mapping["time_s"]) > 1e-6):
            raise ValueError("Original tunnel Native/Core/video join differs")
    observation = measure(context, source_rows)
    measured = measure_tunnel_approach(observation)
    channels = root / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    for name in CHANNELS:
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for row in source_rows:
                value = {"native_frame": row["native_frame"],
                         "body_xy_m": row["body_xy_m"],
                         "incoming_lane_sight_ray": row["incoming_lane_sight_ray"],
                         "one_way_native_survey": context["one_way_native_survey"],
                         "legal_view_obstructed": "independent_judgment_required"}
                stream.write(json.dumps({"time_s": row["time_s"], "value": value},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": "structured", "reference":
                         "channels/" + path.name})
    evidence.append({"name": "tunnel_source_context", "unit": "structured",
                     "reference": "tunnel-context.json"})
    result = {"case_id": config["selected_case_id"],
        "measured_values": measured,
        "target_checks": [{"target": "whole-body left of centre within 100 ft of tunnel",
            "requested": config["requested_left_side"],
            "measured": measured["left_of_centre_within_zone_frames"] > 0,
            "method": "source-bound tunnel approach measurement",
            "tolerance": "none; legal view obstruction remains a judgment",
            "matched": False, "physical_cause_confirmed": False,
            "cause_evidence": list(SOURCE_FILES)}],
        "setup_confirmed": False, "behavior_attempted": not diagnostic,
        "maneuver_completed": False,
        "termination_reason": "600 saved frames measured; original physical review pending",
        "physical_failure_flags": ["Tunnel identity, obstruction, pixels and lateral motion need original review"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": evidence,
        "realized_observables": {},
        "provenance_kind": provenance["provenance_kind"],
        "diagnostic_fixture": diagnostic,
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    source_hashes = {name: sha(required(root, name)) for name in SOURCE_FILES
                     if name != "road.xodr"}
    report = {"format": "worker-tunnel-selected-measurement",
        "case_id": config["selected_case_id"],
        "measurements": {"tunnel_approach": {
            "method": "measure_tunnel_approach", "value": measured,
            "sources": source_hashes}},
        "measurement": observation,
        "legal_compliance": "unassessed", "physical_acceptance_claimed": False}
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
