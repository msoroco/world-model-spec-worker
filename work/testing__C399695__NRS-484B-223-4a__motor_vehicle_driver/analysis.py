"""Saved-only original right-turn-lane purpose, occupancy and route observations."""

import argparse
import hashlib
import json
from pathlib import Path

from package_spec import CAMERA_NAMES
from right_turn_lane_probe import measure


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def source_sealed_right_turn_measurement(value):
    return value


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(source(root, "config.json").read_text())
    case = config["selected_case_id"]
    receipt = json.loads(source(root, "original-source-receipt.json").read_text())
    diagnostic = receipt.get("diagnostic_fixture") is True
    need(receipt.get("source_kind") == ("synthetic_diagnostic_fixture" if diagnostic else "original_native_capture") and receipt.get("case_id") == case,
         "exact original/diagnostic source receipt differs")
    history_path = source(root, "right-turn-history.json")
    trace_path = source(root, "trace.jsonl")
    frame_path = source(root, "video_frames.jsonl")
    measurement_path = source(root, "right-turn-measurement.json")
    for key, path in (("history_sha256", history_path), ("trace_sha256", trace_path),
                      ("frame_map_sha256", frame_path), ("measurement_sha256", measurement_path)):
        need(receipt.get(key) == sha(path), "sealed right-turn source differs: " + key)
    history = json.loads(history_path.read_text())
    rows = history["samples"]
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    frame_map = [json.loads(line) for line in frame_path.read_text().splitlines()]
    need(history.get("assignment_id") == config["assignment_id"] and history.get("case_id") == case and len(rows) == len(trace) == len(frame_map) and len(rows) >= 3,
         "right-turn source row identity/count differs")
    for index, (row, mapped, motion) in enumerate(zip(rows, frame_map, trace)):
        need(row["frame"] == mapped["video_frame"] == index and mapped["native_frame"] == mapped["carla_frame"] == motion["frame"] == row["original_frame"] and
             row["time_s"] == mapped["time_s"] == motion["time_s"] and abs(motion["speed_mps"] - row["speed_mps"]) < 1e-6 and
             row["driver_id"] == history["driver_actor_id"],
             "source frame, trace, driver or motion differs")
    probe_site = {"highway_source": history["highway_source"],
                  "turn_lane_id": history["turn_lane_id"],
                  "turn_lane_source": history["turn_lane_source"],
                  "one_right_turn_lane": history["one_right_turn_lane"],
                  "exclusive_right_turn": history["exclusive_right_turn"],
                  "t_junction_id": history["t_junction_id"],
                  "entry_road_id": history["entry_road_id"],
                  "right_exit_road_id": history["right_exit_road_id"],
                  "connected_route_source": history["connected_route_source"],
                  "ego_id": history["driver_actor_id"]}
    frames = [{"original_frame": row["original_frame"], "time_s": row["time_s"],
               "lane_id": row["lane_id"], "road_id": row["road_id"],
               "maneuver": row["maneuver"], "source_ref": row["source_ref"],
               "driver_id": row["driver_id"]} for row in rows]
    measured = measure(probe_site, frames, history["purpose_declaration"])
    need(json.loads(measurement_path.read_text()) == measured,
         "original route measurement differs from source frames")
    values = {
        "public_highway_and_lane_design": {"public_highway": history["public_highway"],
            "single_exclusive_right_turn_lane": history["one_right_turn_lane"] and history["exclusive_right_turn"],
            "highway_source": history["highway_source"], "turn_lane_source": history["turn_lane_source"]},
        "vehicle_and_driver_identity": {"ego_actor_id": history["ego_actor_id"],
                                         "driver_actor_id": history["driver_actor_id"]},
        "right_turn_lane_occupancy": {"original_frames": measured["lane_occupancy_original_frames"],
                                      "turn_lane_id": history["turn_lane_id"]},
        "declared_maneuver_purpose": {"declared_purpose": measured["declared_purpose"],
                                      "source": measured["purpose_source"],
                                      "declared_before_frame": history["purpose_declaration"]["declared_before_frame"]},
        "connected_right_turn_route": {"entry_road_id": history["entry_road_id"],
                                        "right_exit_road_id": history["right_exit_road_id"],
                                        "source": history["connected_route_source"]},
        "observed_departure_route": {"connected_right_turn_observed": measured["connected_right_turn_observed"],
                                     "source_refs": measured["route_sources"],
                                     "requested_route": history["requested_departure_route"]},
        "vehicle_motion": {"first_position_m": trace[0]["position_m"],
                           "last_position_m": trace[-1]["position_m"],
                           "maximum_speed_mps": max(row["speed_mps"] for row in rows)}}
    contract_sources = {name: sha(source(root, name)) for name in
                        ("right-turn-history.json", "original-source-receipt.json", "trace.jsonl")}
    measurements = {name: {"method": "source_sealed_right_turn_measurement",
                           "value": source_sealed_right_turn_measurement(value),
                           "sources": contract_sources} for name, value in values.items()}
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        output = root / ("channel-" + name + ".jsonl")
        content = "".join(json.dumps({"time_s": row["time_s"], "value":
                                      row["lane_id"] if name == "right_turn_lane_occupancy" else
                                      row["road_id"] if name == "observed_departure_route" else
                                      row["position_xyz_m"] if name == "vehicle_motion" else values[name]}, sort_keys=True) + "\n"
                          for row in rows)
        if output.exists():
            need(output.read_text() == content, "derived channel differs from saved source")
        else:
            output.write_text(content)
        evidence.append({"name": name, "unit": channel["unit"], "reference": output.name})
    context = root / "channel-reviewed_t_junction_site.json"
    content = json.dumps({"reviewed_t_junction_site": {
        "reviewed_site_sha256": history["reviewed_site_sha256"],
        "highway_source": history["highway_source"],
        "connected_route_source": history["connected_route_source"]}}, sort_keys=True) + "\n"
    if context.exists():
        need(context.read_text() == content, "reviewed T junction context differs")
    else:
        context.write_text(content)
    evidence.append({"name": "reviewed_t_junction_site", "unit": "source record",
                     "reference": context.name})
    target = {"target": "source-reviewed right-turn-lane purpose and departure",
              "requested": config["case"]["requested_departure_route"],
              "measured": measured["connected_right_turn_observed"],
              "method": "original Native lane/road frames and pre-entry purpose source",
              "tolerance": 0, "matched": bool(measured["lane_occupancy_original_frames"]),
              "physical_cause_confirmed": False, "cause_evidence": contract_sources}
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case, "measured_values": values, "target_checks": [target],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "saved physical and source review pending",
              "physical_failure_flags": ["physical_acceptance_unverified"],
              "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in CAMERA_NAMES],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case,
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements, "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Lane occupancy and completed turn do not replace independent pre-entry purpose review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
