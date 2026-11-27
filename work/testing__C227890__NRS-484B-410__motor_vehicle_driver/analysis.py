"""Saved-only parked departure analysis from sealed original sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_original_attempt import audit
from parked_activity import measure_original_activity

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_NAMES = ("activity.jsonl", "activity-seal.json", "frame-map.json", "site.json", "actors.json")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + str(path))
    return path


def _rows(path):
    return [json.loads(line) for line in _require(path).read_text().splitlines() if line.strip()]


def measure_parked_departure(source, case_id):
    source = Path(source)
    checked = audit(source, case_id)
    measured = measure_original_activity(source / "activity.jsonl",
                                         source / "activity-seal.json", case_id,
                                         diagnostic=checked["frame_count"] == 9)
    return checked, measured


def build(attempt):
    attempt = Path(attempt)
    config = json.loads(_require(attempt / "config.json").read_text())
    construction = json.loads(_require(attempt / "construction.json").read_text())
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("saved construction case differs")
    source = attempt / "original-attempt"
    for name in SOURCE_NAMES:
        if not (source / name).is_file() or (source / name).is_symlink():
            raise ValueError("Missing required source: original-attempt/" + name)
    checked, measured = measure_parked_departure(source, case_id)
    frames = json.loads(_require(source / "frame-map.json").read_text())["frames"]
    activity = _rows(source / "activity.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    video = _rows(attempt / "video_frames.jsonl")
    if not len(trace) == len(video) == len(frames) == len(activity) == checked["frame_count"]:
        raise ValueError("original parked-departure episode incomplete")
    for index, (mapped, frame, state, graph) in enumerate(zip(video, frames, activity, trace)):
        if (mapped.get("video_frame") != index or
                mapped.get("carla_frame") != frame["native_frame"] or
                mapped.get("time_s") != frame["native_time_s"] or
                state["frame"] != index or graph.get("frame") != frame["native_frame"] or
                graph.get("time_s") != frame["native_time_s"]):
            raise ValueError("original parked-departure frame join differs")
    for view in VIEWS:
        _require(attempt / (view + ".mkv"))
    sources = {"original-attempt/" + name: _sha(source / name) for name in SOURCE_NAMES}
    value = {
        "parked_intervals_s": measured["intervals_s"]["parked"],
        "movement_intervals_s": measured["intervals_s"]["moving"],
        "approach_intervals_s": measured["intervals_s"]["other_approaching"],
        "path_overlap_intervals_s": measured["intervals_s"]["paths_overlap"],
        "minimum_body_center_gap_m": measured["body_center_gap_min_m"],
        "legal_safety_judgment": "unreviewed",
    }
    outputs = {"parked_requirement_0": {"method": "measure_parked_departure",
                                        "value": value,
                                        "sources": {key: sources[key] for key in
                                                    ("original-attempt/activity.jsonl",
                                                     "original-attempt/activity-seal.json",
                                                     "original-attempt/frame-map.json",
                                                     "original-attempt/site.json",
                                                     "original-attempt/actors.json")}}}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": outputs, "analysis_complete": True,
              "legal_verdict_claimed": False, "source_audit": checked,
              "limitations": ["Actual legal parking and movement safety require independent original source review."]}
    return report, construction, config, activity, video, measured, sources


def write_result(attempt, built):
    from worker_exchange.native_output import validate_result
    report, construction, config, activity, video, measured, sources = built
    attempt = Path(attempt)
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    values = {
        "highway_public_status": [row["ego_on_public_highway"] for row in activity],
        "parking_permission": [row["parking_permitted_at_time"] for row in activity],
        "parked_not_exchange": [{"in_bay": row["ego_in_reviewed_parking_bay"],
                                 "speed_mps": row["ego_speed_mps"],
                                 "passenger_exchange": row["passenger_exchange"],
                                 "goods_exchange": row["goods_exchange"]} for row in activity],
        "driver_control": [row["driver_in_control"] for row in activity],
        "approach_vehicle": [{"approaching": row["other_approaching"],
                              "xy_m": row["other_center_xy_m"],
                              "speed_mps": row["other_speed_mps"]} for row in activity],
        "departure_safety": [{"ego_xy_m": row["ego_center_xy_m"],
                              "ego_speed_mps": row["ego_speed_mps"],
                              "paths_overlap": row["paths_overlap"]} for row in activity],
        "four_original_cameras": [{"video_frame": row["video_frame"],
                                   "native_frame": row["carla_frame"]} for row in video],
    }
    evidence = []
    names = [channel["name"] for channel in construction["recording_description"]["channels"]]
    if set(names) != set(values):
        raise ValueError("original parked-departure channel inventory differs")
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        destination = channels / (name + ".jsonl")
        destination.write_text("\n".join(json.dumps({"time_s": index / 20, "value": value}, sort_keys=True)
                                         for index, value in enumerate(values[name])) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(destination.relative_to(attempt))})
    context = channels / "context.json"
    site = json.loads((attempt / "original-attempt/site.json").read_text())
    context.write_text(json.dumps({"reviewed_parked_highway_packet": {
        "source_sha256": sources["original-attempt/site.json"],
        "source_kind": site["source_kind"],
        "public_highway_status": site.get("public_highway_status", False),
        "parking_permitted_at_capture_time": site.get("parking_permitted_at_capture_time", False)},
        "legal_review": "unreviewed"}, sort_keys=True) + "\n")
    for item in construction["recording_description"].get("context_inputs", []):
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(attempt))})
    intervals = measured["intervals_s"]
    target = {"target": "original parked highway departure with another vehicle approach",
              "requested": config["variant"],
              "measured": {"parked_intervals_s": intervals["parked"],
                           "moving_intervals_s": intervals["moving"],
                           "approach_intervals_s": intervals["other_approaching"]},
              "method": "measure_parked_departure", "tolerance": None,
              "matched": False, "physical_cause_confirmed": False,
              "cause_evidence": sources}
    result = {
        "case_id": config["selected_case_id"],
        "measured_values": {key: item["value"] for key, item in report["measurements"].items()},
        "target_checks": [target], "setup_confirmed": False,
        "behavior_attempted": bool(intervals["moving"]), "maneuver_completed": False,
        "termination_reason": "Original motion measured; physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [view + ".mkv" for view in VIEWS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": construction["recording_description"],
        "recording_evidence": evidence,
        "realized_observables": {"sampled_minimum_body_center_gap_m": {
            "value": measured["body_center_gap_min_m"], "unit": "m",
            "method": "source-sealed 20 Hz original activity",
            "time_window": "full diagnostic or original episode", "statistic": "minimum",
            "reference": "channels/approach_vehicle.jsonl", "source_refs": sources}},
        "physical_checks": {"setup": {"status": "unverified", "reason": "public highway and parking source review pending"},
                            "target": {"status": "unverified", "reason": "measured motion does not prove safety"},
                            "maneuver": {"status": "unverified", "reason": "original physical review pending"}},
        "provenance_kind": "synthetic_fixture" if report["source_audit"]["diagnostic_fixture"] else "native",
        "diagnostic_fixture": report["source_audit"]["diagnostic_fixture"],
        "physical_acceptance_claimed": False,
    }
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.attempt / "result.json").exists() or args.output.exists():
        raise ValueError("refusing to overwrite original parked-departure analysis")
    built = build(args.attempt)
    result = write_result(args.attempt, built)
    report = built[0]
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
