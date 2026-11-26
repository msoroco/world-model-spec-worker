"""Saved-only right-pass observations, preserving unresolved safety judgment."""

import argparse
import hashlib
import json
from pathlib import Path

from package_spec import CAMERA_NAMES
from right_pass import measure


def need(ok, message):
    if not ok:
        raise ValueError(message)


def source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_sealed_right_pass_measurement(value):
    return value


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(source(root, "config.json").read_text())
    case = config["selected_case_id"]
    history_path = source(root, "right-pass-history.json")
    receipt_path = source(root, "original-source-receipt.json")
    trace_path = source(root, "trace.jsonl")
    frame_path = source(root, "video_frames.jsonl")
    receipt = json.loads(receipt_path.read_text())
    diagnostic = receipt.get("diagnostic_fixture") is True
    need(receipt.get("source_kind") == ("synthetic_diagnostic_fixture" if diagnostic else
                                       "original_native_capture") and
         receipt.get("case_id") == case and
         receipt.get("history_sha256") == sha(history_path) and
         receipt.get("trace_sha256") == sha(trace_path) and
         receipt.get("frame_map_sha256") == sha(frame_path),
         "sealed right-pass sources differ")
    history = json.loads(history_path.read_text())
    need(history.get("case_id") == case and
         history.get("assignment_id") == config["assignment_id"],
         "exact right-pass history identity differs")
    rows = history["samples"]
    traces = [json.loads(line) for line in trace_path.read_text().splitlines()]
    maps = [json.loads(line) for line in frame_path.read_text().splitlines()]
    need(len(rows) == len(traces) == len(maps) and len(rows) >= 3,
         "right-pass source frame count differs")
    for index, (row, trace, mapped) in enumerate(zip(rows, traces, maps)):
        need(row.get("frame") == mapped.get("video_frame") == index and
             row.get("native_frame") == trace.get("frame") ==
             mapped.get("native_frame") == mapped.get("carla_frame") and
             row.get("time_s") == trace.get("time_s") == mapped.get("time_s"),
             "right-pass body/trace/video frame identity differs")
    try:
        facts = measure(history)
        gap = None
    except ValueError as error:
        facts = None
        gap = str(error)
    values = {
        "qualifying_vehicles_and_driver": {"actor_ids": history["actor_ids"],
                                           "driver_actor_id": history.get("driver_actor_id"),
                                           "ego_actor_id": history["actor_ids"][0],
                                           "target_actor_id": history["actor_ids"][1]},
        "right_lane_and_pavement": {"map_sha256": history["map_sha256"],
                                    "right_lane_same_direction": history.get("right_lane_same_direction"),
                                    "paved_boundary_source": history.get("paved_boundary_source")},
        "whole_right_pass": {"passing_frames": facts["passing_frames"] if facts else [],
                             "physical_gap": gap},
        "approach_space": {"minimum_body_gap_m": facts["minimum_approach_body_gap_m"] if facts else None,
                            "minimum_ttc_s": facts["minimum_approach_ttc_s"] if facts else None,
                            "physical_gap": gap},
        "lateral_space": {"minimum_body_clearance_m": facts["minimum_lateral_body_clearance_m"] if facts else None,
                          "physical_gap": gap},
        "conflict_space": {"actor_present": len(history["actor_ids"]) == 3,
                           "minimum_body_distance_m": facts["minimum_conflict_body_distance_m"] if facts else None,
                           "physical_gap": gap},
        "motion_context": {"frame_count": len(rows),
                           "ego_speed_mps": [row["ego_speed_mps"] for row in rows],
                           "ego_controls": [row.get("ego_control") for row in rows]}}
    source_hashes = {name: sha(source(root, name)) for name in
                     ("right-pass-history.json", "original-source-receipt.json", "trace.jsonl")}
    measurements = {name: {"method": "source_sealed_right_pass_measurement",
                           "value": source_sealed_right_pass_measurement(value),
                           "sources": source_hashes}
                    for name, value in values.items()}
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        target = root / ("channel-" + name + ".jsonl")
        content = "".join(json.dumps({"time_s": row["time_s"],
            "value": row.get("ego_speed_mps") if name == "motion_context" else
            row.get("ego_body_s_bounds_m") if name == "whole_right_pass" else
            row.get("target_body_s_bounds_m") if name == "approach_space" else
            row.get("ego_body_y_bounds_m") if name == "lateral_space" else
            row.get("conflict_body_s_bounds_m", []) if name == "conflict_space" else
            history.get("map_sha256") if name == "right_lane_and_pavement" else
            row.get("actor_ids")}, sort_keys=True) + "\n" for row in rows)
        if target.exists():
            need(target.read_text() == content, "derived right-pass channel differs")
        else:
            target.write_text(content)
        evidence.append({"name": name, "unit": channel["unit"], "reference": target.name})
    context = root / "channel-reviewed_native_right_pass_site.json"
    content = json.dumps({"reviewed_native_right_pass_site": {
        "map_sha256": history["map_sha256"],
        "reviewed_site_sha256": history.get("reviewed_site_sha256"),
        "paved_boundary_source": history.get("paved_boundary_source")}}, sort_keys=True) + "\n"
    if context.exists():
        need(context.read_text() == content, "reviewed right-pass context differs")
    else:
        context.write_text(content)
    evidence.append({"name": "reviewed_native_right_pass_site", "unit": "source record",
                     "reference": context.name})
    target = {"target": "source-sealed original right-side passing history",
              "requested": case.removeprefix(config["assignment_id"] + "__"),
              "measured": history.get("variant"), "method": "original actor and map readback",
              "tolerance": 0, "matched": history.get("variant") ==
              case.removeprefix(config["assignment_id"] + "__"),
              "physical_cause_confirmed": False, "cause_evidence": source_hashes}
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case, "measured_values": values, "target_checks": [target],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "saved physical/legal review pending",
              "physical_failure_flags": ["physical_acceptance_unverified"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERA_NAMES],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "diagnostic_fixture": diagnostic,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case,
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements, "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Safety condition remains an unresolved legal judgment."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
