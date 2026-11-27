"""Saved taxi source finalizer with explicit source and case joins.

This records measured geometry and independently reviewed activity. It never
decides whether a passenger exchange was legally expeditious.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from taxi_stand_measurement import ASSIGNMENT, measure


def source(attempt: Path, name: str) -> Path:
    path = attempt / name
    if not path.is_file() or not path.resolve().is_relative_to(attempt.resolve()):
        raise ValueError("Missing required source: " + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trace_row(index: int, row: dict) -> dict:
    x, y = row["taxi_center_xy_m"]
    return {"frame": row.get("native_frame", index), "time_s": row["elapsed_s"],
            "position": {"x": x, "y": y, "z": 0.0},
            "position_m": [x, y, 0.0],
            "heading_deg": 0.0, "speed_mps": row["taxi_speed_mps"],
            "speed_mph": row["taxi_speed_mps"] / 0.44704,
            "velocity_mps": [0.0,0.0,0.0], "road_id": 10,
            "control": {"throttle": 0.0, "brake": 1.0,
                        "hand_brake": True, "steer": 0.0}}


def measure_stand_context(observation: dict) -> dict:
    return {"all_halt_footprints_inside_designated_stand":
            observation["all_halt_footprints_inside_designated_stand"],
            "all_halt_footprints_outside_designated_stand":
            observation["all_halt_footprints_outside_designated_stand"],
            "source_sha256": observation["source_sha256"]}


def measure_standing_or_parking(observation: dict) -> dict:
    return {"reviewed_activity": observation["reviewed_activity"],
            "halt_interval_frames": observation["halt_interval_frames"],
            "max_halt_speed_mps": observation["max_halt_speed_mps"],
            "footprints_outside_stand":
            observation["all_halt_footprints_outside_designated_stand"]}


def measure_passenger_exception(observation: dict) -> dict:
    return {"reviewed_activity": observation["reviewed_activity"],
            "passenger_event_kinds": observation["passenger_event_kinds"],
            "halt_interval_frames": observation["halt_interval_frames"],
            "expeditiousness_review_required": True,
            "other_regulation_review_required": True}


def write_saved_outputs(attempt: Path, packet: dict, observation: dict) -> None:
    """Project sealed source rows into the runtime's recording shape."""
    construction = json.loads(source(attempt, "construction.json").read_text())
    description = construction["recording_description"]
    frames = json.loads(source(attempt, "native_frames.json").read_text())
    if not isinstance(frames, list) or len(frames) != 900:
        raise ValueError("Full saved Native frame history required")
    activity = json.loads(source(attempt, "activity_review.json").read_text())
    videos = [name + ".mkv" for name in ("overview", "approach",
                                           "reference_corner", "driver_reference")]
    video_hashes = {name: sha(source(attempt, name)) for name in videos}
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    traces = []
    maps = []
    values = {name: [] for name in (item["name"] for item in description["channels"])}
    for index, row in enumerate(frames):
        time_s = row["elapsed_s"]
        native_frame = row.get("native_frame", index)
        x, y = row["taxi_center_xy_m"]
        traces.append(trace_row(index, row))
        maps.append({"video_frame": index, "carla_frame": native_frame,
                     "native_frame": native_frame, "time_s": time_s})
        by_name = {"native_frame": native_frame,
                   "taxi_center_xy_m": [x,y],
                   "taxi_footprint_xy_m": row["taxi_footprint_xy_m"],
                   "taxi_speed_mps": row["taxi_speed_mps"],
                   "four_camera_frames": {"video_frame": index,
                                           "sha256": video_hashes},
                   "passenger_activity_review": {"reviewer_id": activity["reviewer_id"],
                                                 "passenger_events": activity["passenger_events"]}}
        for name in values:
            values[name].append({"time_s": time_s, "value": by_name[name]})
    (attempt / "trace.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in traces))
    mapping_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in maps)
    mapping_path = attempt / "video_frames.jsonl"
    if mapping_path.exists():
        if mapping_path.read_text() != mapping_text:
            raise ValueError("Original camera frame map differs from saved taxi history")
    else:
        mapping_path.write_text(mapping_text)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        path = channels / (name + ".jsonl")
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in values[name]))
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": str(path.relative_to(attempt))})
    contexts = {"taxi_stand_designation": observation["source_sha256"]["stand_designation"],
                "business_district_and_street": observation["source_sha256"]["reviewed_site"],
                "taxi_licence_and_operator": observation["source_sha256"]["taxi_licence"],
                "other_stopping_parking_regulations": observation["source_sha256"]["other_regulations"]}
    context_path = channels / "source_context.json"
    context_path.write_text(json.dumps(contexts, indent=2, sort_keys=True) + "\n")
    evidence.extend({"name": item["name"], "unit": item["unit"],
                     "reference": str(context_path.relative_to(attempt))}
                    for item in description["context_inputs"])
    actual_location = ("in_stand" if observation["all_halt_footprints_inside_designated_stand"]
                       else "outside_stand" if observation["all_halt_footprints_outside_designated_stand"]
                       else "stand_boundary_overlap")
    planned = next(case for case in json.loads(source(attempt, "case-plan.json").read_text())["cases"]
                   if case["case_id"] == packet["case_id"])
    target = {"target": "reviewed taxi halt footprint relative to designated stand",
              "requested": planned["location_request"], "measured": actual_location,
              "method": "saved complete taxi-body footprint and source-hashed stand polygon",
              "tolerance": 0, "matched": planned["location_request"] == actual_location,
              "physical_cause_confirmed": False,
              "cause_evidence": observation["source_sha256"]}
    result = {"case_id": packet["case_id"],
              "measured_values": {"taxi_location": actual_location,
                                  "reviewed_activity": observation["reviewed_activity"],
                                  "passenger_event_kinds": observation["passenger_event_kinds"]},
              "target_checks": [target],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "diagnostic saved-source assessment; original physical acceptance pending",
              "physical_failure_flags": {"original_capture_unreviewed": True},
              "trace_reference": "trace.jsonl", "video_references": videos,
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {},
              "provenance_kind": "synthetic_fixture" if packet.get("diagnostic_fixture") else "original_native",
              "diagnostic_fixture": packet.get("diagnostic_fixture") is True}
    (attempt / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def analyze(attempt: Path, output: Path) -> dict:
    attempt = attempt.resolve()
    packet_path = source(attempt, "taxi-source-packet.json")
    packet = json.loads(packet_path.read_text())
    case_id = packet.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("Exact taxi case identity required")
    config = json.loads(source(attempt, "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("Saved taxi case differs from selected construction")
    for name in ("native_frames.json", "activity_review.json", "reviewed_site.json",
                 "native_result.json", "stand_designation.json", "taxi_licence.json",
                 "other_regulations.json"):
        source(attempt, name)
    observation = measure(packet, attempt)
    method_specs = [("taxi_stand_context", measure_stand_context),
                    ("taxi_halt_activity", measure_standing_or_parking)
                    if case_id.endswith(("__designated_stand_park", "__outside_stand_park",
                                         "__outside_stand_stand"))
                    else ("taxi_passenger_exception", measure_passenger_exception)]
    inputs = ["taxi-source-packet.json", "native_frames.json", "activity_review.json",
              "reviewed_site.json", "native_result.json", "stand_designation.json",
              "taxi_licence.json", "other_regulations.json"]
    hashes = {name: sha(source(attempt, name)) for name in inputs}
    report = {"format": "worker-taxi-source-analysis", "case_id": case_id,
              "measurements": {key: {"method": method.__name__, "value": method(observation),
                                     "sources": hashes}
                               for key, method in method_specs},
              "observation": observation,
              "legal_verdict": None,
              "scope": "Saved source measurements; legal expeditiousness and original authenticity require independent acceptance"}
    if output.name != "analysis-report.json":
        raise ValueError("Analysis output must be analysis-report.json")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_saved_outputs(attempt, packet, observation)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    analyze(args.attempt, args.output)
