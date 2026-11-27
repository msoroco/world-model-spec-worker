"""Saved-only finalizer for original approach and right-turn lane position."""

import argparse
import hashlib
import json
from pathlib import Path

from package_spec import CAMERA_NAMES
from turn_position import measure


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def source_sealed_turn_position(value):
    return value


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(_source(root, "config.json").read_text())
    case = config["selected_case_id"]
    receipt = json.loads(_source(root, "original-source-receipt.json").read_text())
    diagnostic = receipt.get("diagnostic_fixture") is True
    _need(receipt.get("source_kind") == ("synthetic_diagnostic_fixture" if diagnostic else "original_native_capture")
          and receipt.get("case_id") == case, "exact original/diagnostic source receipt differs")
    paths = {name: _source(root, name) for name in
             ("turn-position-history.json", "turn-position-measurement.json", "trace.jsonl", "video_frames.jsonl")}
    for field, name in (("history_sha256", "turn-position-history.json"),
                        ("measurement_sha256", "turn-position-measurement.json"),
                        ("trace_sha256", "trace.jsonl"), ("frame_map_sha256", "video_frames.jsonl")):
        _need(receipt.get(field) == _sha(paths[name]), "sealed turn-position source differs: " + field)
    history = json.loads(paths["turn-position-history.json"].read_text())
    trace, mapping = _rows(paths["trace.jsonl"]), _rows(paths["video_frames.jsonl"])
    samples = history["samples"]
    _need(history.get("assignment_id") == config["assignment_id"] and history.get("case_id") == case and
          len(samples) == len(trace) == len(mapping) and len(samples) >= 4,
          "turn-position original source identity/count differs")
    frames = []
    for index, (row, motion, mapped) in enumerate(zip(samples, trace, mapping)):
        _need(row["frame"] == mapped["video_frame"] == index and
              row["native_frame"] == row["original_frame"] == mapped["native_frame"] == mapped["carla_frame"] == motion["frame"] and
              row["time_s"] == mapped["time_s"] == motion["time_s"] and
              row["driver_id"] == history["driver_actor_id"] and
              row["position_xyz_m"] == motion["position_m"] and
              abs(row["speed_mps"] - motion["speed_mps"]) < 1e-6,
              "original frame, motion, body or driver join differs")
        frames.append({key: row[key] for key in
                       ("original_frame", "time_s", "driver_id", "road_id", "lane_id",
                        "junction_id", "phase", "source_ref", "position_xyz_m")})
    site = {key: history[key] for key in
            ("map_sha256", "public_highway_source", "intersection_source",
             "right_lane_design_source", "qualification_223_4_source",
             "connected_right_exit_source", "turn_phase_lane_source",
             "turn_phase_lane_refs", "driver_identity_source", "entry_road_id",
             "right_exit_road_id", "junction_id", "turn_lane_id", "extreme_right_lane_id",
             "public_highway", "non_alley_intersection", "t_intersection",
             "connected_right_exit", "right_turn_lane_qualified_under_223_4")}
    site["source_id"] = history["reviewed_site_sha256"]
    site["driver_id"] = history["driver_actor_id"]
    measured = measure(site, frames, history["intended_maneuver"])
    _need(json.loads(paths["turn-position-measurement.json"].read_text()) == measured,
          "turn-position measurement differs from original frames")
    values = {
        "intersection_and_highway": {"public_highway": history["public_highway"],
                                     "non_alley_intersection": history["non_alley_intersection"],
                                     "connected_right_exit": history["connected_right_exit"]},
        "conditional_lane_qualification": {"qualifying_right_turn_lane": measured["qualifying_right_turn_lane"],
                                           "conditional_lane_id": measured["conditional_lane_id"],
                                           "required_turn_phase_lane_refs": measured["required_turn_phase_lane_refs"]},
        "extreme_right_alternative": {"qualifying_right_turn_lane": measured["qualifying_right_turn_lane"],
                                       "extreme_right_lane_id": history["extreme_right_lane_id"],
                                       "conditional_lane_id": measured["conditional_lane_id"]},
        "driver_and_intention": {"driver_id": history["driver_actor_id"],
                                 "intention_source": measured["intention_source"]},
        "approach_lane_position": {"lane_ids": measured["approach_lane_ids"],
                                   "original_frames": measured["approach_original_frames"],
                                   "entirely_from_required_lane": measured["approach_entirely_from_required_lane"]},
        "turn_lane_position": {"lane_ids": measured["turn_lane_ids"],
                               "original_frames": measured["turn_original_frames"],
                               "entirely_from_required_lane": measured["turn_entirely_from_required_lane"]},
        "connected_departure": {"right_exit_road_id": history["right_exit_road_id"],
                                "observed_exit_road_id": samples[-1]["road_id"]},
    }
    source_hashes = {name: _sha(_source(root, name)) for name in
                     ("turn-position-history.json", "original-source-receipt.json", "trace.jsonl")}
    measurements = {name: {"method": "source_sealed_turn_position",
                           "value": source_sealed_turn_position(value),
                           "sources": source_hashes} for name, value in values.items()}
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        path = root / ("channel-" + name + ".jsonl")
        content = "".join(json.dumps({"time_s": row["time_s"], "value":
                                      row["lane_id"] if name in ("approach_lane_position", "turn_lane_position") else
                                      row["road_id"] if name == "connected_departure" else values[name]}, sort_keys=True) + "\n"
                          for row in samples)
        if path.exists():
            _need(path.read_text() == content, "derived channel differs from saved source")
        else:
            path.write_text(content)
        evidence.append({"name": name, "unit": channel["unit"], "reference": path.name})
    context = root / "channel-reviewed_t_junction_site.json"
    content = json.dumps({"reviewed_t_junction_site": {
        "reviewed_site_sha256": history["reviewed_site_sha256"],
        "qualification_source": history["qualification_223_4_source"]}}, sort_keys=True) + "\n"
    if context.exists():
        _need(context.read_text() == content, "reviewed site context differs")
    else:
        context.write_text(content)
    evidence.append({"name": "reviewed_t_junction_site", "unit": "source record",
                     "reference": context.name})
    target = {"target": "measured right-turn approach and turn lane position",
              "requested": config["case"]["case_id"],
              "measured": {"approach": measured["approach_entirely_from_required_lane"],
                           "turn": measured["turn_entirely_from_required_lane"]},
              "method": "original Native joined lane/road/pose and independent qualification source",
              "tolerance": 0, "matched": True,
              "physical_cause_confirmed": False, "cause_evidence": source_hashes}
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case, "measured_values": values, "target_checks": [target],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "saved physical and source review pending",
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
    return {"format": "worker-analysis-report", "case_id": case,
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements, "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Measured lane intervals and reviewed design are observations, not a legal verdict."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
