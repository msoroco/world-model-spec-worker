"""Saved-source curb-entry measurement for pinned runtime compatibility."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from curb_entry import CASES, measure_original
from delivery_audit import ASSIGNMENT


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pedestrian_path_entry_observation(attempt: Path, case_id: str) -> dict:
    site_path, trace_path = attempt / "site.json", attempt / "trace.json"
    for path in (site_path, trace_path):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    case = next((item for item in CASES if case_id == ASSIGNMENT + "__" + item.name), None)
    if case is None:
        raise ValueError("exact selected pedestrian case required")
    site = json.loads(site_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if trace.get("case_id") != case_id:
        raise ValueError("saved trace case identity differs")
    scene = site.get("scenes", {}).get(case.name)
    if not isinstance(scene, dict):
        raise ValueError("saved exact curb scene missing")
    return measure_original(trace.get("frames", []), scene, case)


def build_report(attempt: Path, case_id: str) -> dict:
    observation = pedestrian_path_entry_observation(attempt, case_id)
    trace = json.loads((attempt / "trace.json").read_text(encoding="utf-8"))
    value = {**observation, "legal_suddenness_or_impossibility": "unresolved"}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {"pedestrian_path_entry_observation": {
                "value": value, "method": "pedestrian_path_entry_observation",
                "sources": {"site.json": sha(attempt / "site.json"),
                            "trace.json": sha(attempt / "trace.json")}}},
            "analysis_complete": True,
            "diagnostic_fixture": trace.get("diagnostic_fixture") is True,
            "legal_verdict_claimed": False}


def saved_result(attempt: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result

    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    if (config["law_id"], config["cell_id"], config["actor"]) != (
            "NRS-484B-283-1b", "C228096", "pedestrian") or construction["case_id"] != case_id:
        raise ValueError("saved assignment or construction identity differs")
    description = construction["recording_description"]
    trace = json.loads((attempt / "trace.json").read_text(encoding="utf-8"))
    rows = trace["frames"]
    channel_values = {
        "pedestrian and curb geometry": [
            {"pedestrian_id": row["pedestrian_id"],
             "pedestrian_xy": row["pedestrian_xy"]} for row in rows],
        "pedestrian and vehicle trajectories": [
            {"pedestrian_xy": row["pedestrian_xy"], "vehicle_xy": row["vehicle_xy"],
             "pedestrian_speed_mps": row["pedestrian_speed_mps"],
             "vehicle_speed_mps": row["vehicle_speed_mps"]} for row in rows],
        "vehicle path and driver": [
            {"vehicle_id": row["vehicle_id"],
             "vehicle_path_source_sha256": row["vehicle_path_source_sha256"],
             "driver_control_source_sha256": row["driver_control_source_sha256"]}
            for row in rows],
        "four synchronized camera views": [
            {"camera_sources": ["overview.mkv", "approach.mkv",
                                "reference_corner.mkv", "driver_reference.mkv"],
             "video_frame": index} for index in range(900)],
    }
    channels = attempt / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        if name not in channel_values:
            raise ValueError("unsupported pedestrian recording channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for index, value in enumerate(channel_values[name]):
                stream.write(json.dumps({"time_s": index / 20, "value": value}) + "\n")
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": str(path.relative_to(attempt))})
    context = {"reviewed curb, roadway and driver authority": {
        "source_kind": "synthetic CPU fixture" if trace.get("diagnostic_fixture")
                       else "original site requires independent delivery audit",
        "physical_reviewed": False}}
    (channels / "context.json").write_text(json.dumps(context) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        if item["name"] not in context:
            raise ValueError("unsupported pedestrian context input")
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": "channels/context.json"})
    observed = report["measurements"]["pedestrian_path_entry_observation"]["value"]
    requested_path = case_id.endswith("_into_path")
    measured_path = observed["vehicle_path_entry_frame"] is not None
    result = {"case_id": case_id, "measured_values": observed,
        "target_checks": [{"target": "entry into vehicle path", "requested": requested_path,
                           "measured": measured_path,
                           "method": "900 original synchronized position readbacks",
                           "tolerance": 0, "matched": requested_path == measured_path,
                           "physical_cause_confirmed": False,
                           "cause_evidence": report["measurements"]["pedestrian_path_entry_observation"]["sources"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved source assessment pending physical review",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": ["overview.mkv", "approach.mkv",
                             "reference_corner.mkv", "driver_reference.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {"pedestrian_path_entry": observed}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh analysis report required")
    case_id = args.case or json.loads((args.attempt / "config.json").read_text())[
        "selected_case_id"]
    report = build_report(args.attempt, case_id)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n",
                                              encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
