"""Saved source-bound overtaking measurements; no legal predicate or acceptance."""

import argparse
import hashlib
import json
from pathlib import Path

from package_spec import CAMERA_NAMES
from pass_measurements import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def measure_activation(observed):
    first = observed["observations"][0]
    return {"qualifying_control_kind": observed["control_kind"],
            "first_frame": first["frame"], "initial_control_ahead_m":
            first["control_rear_station_m"] - first["ego_front_station_m"],
            "first_full_body_pass_frame": observed["first_observed_full_pass_frame"]}


def measure_due_care_sources(observed):
    rows = observed["observations"]
    return {"ego_speed_mps": [row["ego_speed_mps"] for row in rows],
            "control_speed_mps": [row["control_speed_mps"] for row in rows],
            "sampled_frames": [row["frame"] for row in rows],
            "legal_due_care": "unresolved"}


def measure_topology(observed):
    return {"same_direction_lane_count": observed["same_direction_lane_count"],
            "immediate_left_lane_id": observed["immediate_left_lane_id"],
            "initial_ego_lane_id": observed["observations"][0]["ego_lane_id"]}


def measure_lane_movement(observed):
    rows = observed["observations"]
    left = observed["immediate_left_lane_id"]
    first_entry = next((row["frame"] for row in rows if row["ego_lane_id"] == left), None)
    return {"first_immediate_left_entry_frame": first_entry,
            "ego_lane_at_full_pass": observed["ego_lane_at_full_pass"],
            "left_lane_occupied_at_full_pass": observed["left_lane_occupied_at_full_pass"],
            "legal_availability": "unresolved", "legal_reasonable_safety": "unresolved"}


METHODS = (measure_activation, measure_due_care_sources, measure_topology,
           measure_lane_movement)
KEYS = ("activation", "due_care_sources", "lane_topology", "lane_movement")


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case = config["case"]
    context = required(root, "original-context.json")
    trace = required(root, "original-trace.jsonl")
    receipt_path = required(root, "original-source-receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    diagnostic = receipt.get("diagnostic_fixture") is True
    if diagnostic and receipt.get("source_kind") != "synthetic_diagnostic_fixture":
        raise ValueError("diagnostic source provenance mismatch")
    if not diagnostic and receipt.get("source_kind") != "original_native_capture":
        raise ValueError("original Native source provenance missing")
    observed = measure(case_id=config["selected_case_id"], context_path=context,
                       trace_path=trace, receipt_path=receipt_path,
                       allow_diagnostic=diagnostic)
    source_hashes = {name: sha(root / name) for name in
                     ("original-context.json", "original-trace.jsonl",
                      "original-source-receipt.json")}
    relevant = [0, 1, 2] + ([3] if case["same_direction_lane_count_requested"] == 2 else [])
    measurements = {KEYS[i]: {"method": METHODS[i].__name__,
                              "value": METHODS[i](observed),
                              "sources": source_hashes} for i in relevant}
    channel_rows = {
        "ego_control_body": lambda row: {"ego_rear_station_m": row["ego_rear_station_m"],
                                         "ego_front_station_m": row["ego_front_station_m"],
                                         "control_rear_station_m": row["control_rear_station_m"],
                                         "control_front_station_m": row["control_front_station_m"]},
        "lane_topology": lambda row: {"same_direction_lane_count": observed["same_direction_lane_count"],
                                      "ego_lane_id": row["ego_lane_id"],
                                      "immediate_left_lane_id": observed["immediate_left_lane_id"]},
        "left_lane_traffic": lambda row: row["left_lane_occupied_actor_ids"],
        "ego_lane_and_pass": lambda row: {"ego_lane_id": row["ego_lane_id"],
                                          "full_pass_frame": observed["first_observed_full_pass_frame"]},
        "relative_motion": lambda row: {"ego_speed_mps": row["ego_speed_mps"],
                                         "control_speed_mps": row["control_speed_mps"]}}
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        if name == "camera_frame_identity":
            mapping_path = required(root, "video_frames.jsonl")
            data = "".join(json.dumps({"time_s": row["time_s"],
                                       "value": {"frame": row["carla_frame"]}}) + "\n"
                           for row in (json.loads(line) for line in
                                       mapping_path.read_text(encoding="utf-8").splitlines()))
        else:
            if name not in channel_rows:
                raise ValueError("unknown pass observation channel: " + name)
            data = "".join(json.dumps({"time_s": row["time_s"],
                                       "value": channel_rows[name](row)}) + "\n"
                           for row in observed["observations"])
        target = root / ("channel-" + name + ".jsonl")
        if target.exists():
            if target.read_text(encoding="utf-8") != data:
                raise ValueError("derived channel evidence differs from source replay")
        else:
            target.write_text(data, encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": target.name})
    for context_input in config["case"]["recording_description"].get("context_inputs", []):
        if context_input["name"] != "reviewed_native_lane_packet":
            raise ValueError("unknown pass context input")
        target = root / "channel-reviewed_native_lane_packet.json"
        data = json.dumps({"reviewed_native_lane_packet": {
            "source_kind": receipt["source_kind"], "context_sha256": sha(context),
            "receipt_sha256": sha(receipt_path),
            "map_sha256": json.loads(context.read_text())["map_sha256"]}},
            sort_keys=True) + "\n"
        if target.exists():
            if target.read_text(encoding="utf-8") != data:
                raise ValueError("derived context evidence differs from source replay")
        else:
            target.write_text(data, encoding="utf-8")
        evidence.append({"name": context_input["name"], "unit": context_input["unit"],
                         "reference": target.name})
    expected_move = case["ego_maneuver_request"] == "move_left" and \
        case["left_lane_traffic_requested"] == "open"
    expected_pass = case["ego_maneuver_request"] in {"move_left", "stay", "pass"} and \
        case["left_lane_traffic_requested"] != "occupied"
    observed_move = observed["immediate_left_lane_id"] is not None and any(
        row["ego_lane_id"] == observed["immediate_left_lane_id"]
        for row in observed["observations"])
    observed_pass = observed["first_observed_full_pass_frame"] is not None
    from worker_exchange.native_output import physical_result, write_result
    target = {"target": "original requested overtaking and immediate-left lane behavior",
              "requested": {"pass": expected_pass, "move_left": expected_move},
              "measured": {"pass": observed_pass, "move_left": observed_move},
              "method": "source-sealed original full-body pass and lane history",
              "tolerance": 0, "matched": observed_pass == expected_pass and
              observed_move == expected_move, "physical_cause_confirmed": False,
              "cause_evidence": source_hashes}
    result = {"case_id": config["selected_case_id"],
              "measured_values": {"first_observed_full_pass_frame":
                                  observed["first_observed_full_pass_frame"],
                                  "ego_lane_at_full_pass": observed["ego_lane_at_full_pass"]},
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "saved source assessment; physical and legal review pending",
              "physical_failure_flags": ["physical_acceptance_unverified"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERA_NAMES],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": config["selected_case_id"],
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements, "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Source measurements describe observed motion only; due care, availability and reasonable safety need original review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n",
                           encoding="utf-8")
