"""Selected saved-source measurement report; original status is source-gated."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from finalize_follower import finalize
from reviewed_scene import ASSIGNMENT, VARIANTS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def right_lane_follower_observation(attempt: Path, case_id: str) -> dict:
    trace, relation = attempt / "trace.json", attempt / "relation.json"
    for path in (trace, relation):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    return finalize(trace, sha(trace), relation, sha(relation), case_id)


def build_report(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        raise ValueError("exact selected case required")
    observation = right_lane_follower_observation(attempt, case_id)
    trace = json.loads((attempt / "trace.json").read_text(encoding="utf-8"))
    value = {"original_frame_count": observation["original_frame_count"],
             "right_lane_frames": sum(row["ego_in_extreme_right_lane"] for row in observation["observations"]),
             "immediate_follower_frames": sum(row["follower_immediately_behind_in_ego_lane"] for row in observation["observations"]),
             "passing_frames": sum(row["passing_slower_vehicle_observed"] for row in observation["observations"]),
             "legal_impediment_and_pass_necessity": "unresolved"}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {"right_lane_follower_observation": {
                "value": value, "method": "right_lane_follower_observation",
                "sources": {"trace.json": sha(attempt / "trace.json"),
                            "relation.json": sha(attempt / "relation.json")}}},
            "analysis_complete": True,
            "diagnostic_fixture": trace.get("diagnostic_fixture") is True,
            "legal_verdict_claimed": False}


def saved_result(attempt: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    if (config["law_id"], config["cell_id"], config["actor"]) != (
            "NRS-484B-627-1b", "C147344", "motor_vehicle_driver"):
        raise ValueError("saved finalizer assignment identity differs")
    if construction["case_id"] != case_id:
        raise ValueError("saved construction case identity differs")
    description = construction["recording_description"]
    trace = json.loads((attempt / "trace.json").read_text(encoding="utf-8"))
    relation = json.loads((attempt / "relation.json").read_text(encoding="utf-8"))
    observations = right_lane_follower_observation(attempt, case_id)["observations"]
    channel_values = {
        "ego_speed_mps": [row["ego_speed_mps"] for row in trace["frames"]],
        "slower_vehicle_speed_mps": [row["slower_vehicle_speed_mps"]
                                     for row in trace["frames"]],
        "marked highway lane identities": [
            {"rightmost_lane_id": row["rightmost_same_direction_lane_id"],
             "same_direction_marked_lane_count": row["same_direction_marked_lane_count"]}
            for row in trace["frames"]],
        "ego lane and motor-vehicle motion": [
            {"ego_lane_id": row["ego_lane_id"], "ego_speed_mps": row["ego_speed_mps"]}
            for row in trace["frames"]],
        "following traffic and immediate relation": [
            {"follower_actor_id": row["follower_actor_id"],
             "follower_gap_m": row["follower_gap_m"],
             "follower_speed_mps": row["follower_speed_mps"],
             "immediately_behind": relation["samples"][i]["immediately_behind"]}
            for i, row in enumerate(trace["frames"])],
        "passing and slower vehicle": [
            {"passing_slower_vehicle_observed": row["passing_slower_vehicle_observed"]}
            for row in trace["frames"]],
        "four synchronized camera views": [
            {"camera_sources": ["overview.mkv", "approach.mkv",
                                "reference_corner.mkv", "driver_reference.mkv"],
             "video_frame": i} for i in range(900)],
    }
    channels = attempt / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        if name not in channel_values:
            raise ValueError("unsupported selected recording channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for i, value in enumerate(channel_values[name]):
                stream.write(json.dumps({"time_s": i / 20, "value": value}) + "\n")
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_values = {"reviewed original highway and marked-lane authority": {
        "source_kind": "synthetic CPU fixture" if trace.get("diagnostic_fixture") else
                       "original site source requires independent delivery audit",
        "actual_highway_reviewed": False}}
    context_path = channels / "context.json"
    context_path.write_text(json.dumps(context_values) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        if item["name"] not in context_values:
            raise ValueError("unsupported selected recording context: " + item["name"])
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    observed = report["measurements"]["right_lane_follower_observation"]["value"]
    requested_right = case_id.endswith("__slow_right_follower")
    measured_right = observed["right_lane_frames"] == 900
    result = {"case_id": case_id, "measured_values": observed,
        "target_checks": [{"target": "extreme-right lane occupancy", "requested": requested_right,
                           "measured": measured_right, "method": "900 original lane readbacks",
                           "tolerance": 0, "matched": measured_right == requested_right,
                           "physical_cause_confirmed": False,
                           "cause_evidence": report["measurements"]["right_lane_follower_observation"]["sources"]}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved evidence assessment pending physical review",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv",
                             "driver_reference.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {"right_lane_observations": observations}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh analysis report required")
    case_id = args.case or json.loads((args.attempt / "config.json").read_text(encoding="utf-8"))["selected_case_id"]
    report = build_report(args.attempt, case_id)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
