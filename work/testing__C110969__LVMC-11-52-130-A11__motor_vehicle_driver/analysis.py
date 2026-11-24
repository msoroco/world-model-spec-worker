"""Saved-source measurements for the intersection stop/stand branch.

The output describes observed motion and recorded context. It does not decide
necessity, law compliance, direction applicability, or a legal violation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_delivery import audit


SOURCES = ("original-attempt/attempt.json", "original-attempt/pose.jsonl",
           "original-attempt/map-geometry.json", "original-attempt/context.jsonl")


def _required(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Missing required source: " + relative)
    return path


def _rows(root, relative):
    return [json.loads(line) for line in _required(root, relative).read_text().splitlines() if line]


def measure_activity(root, source):
    pose = _rows(root, "original-attempt/pose.jsonl")
    halts = source["measurement"]["halt_intervals"]
    return {"observed_halt_intervals": halts, "halt_samples": sum(bool(r["halt_state"]) for r in pose),
            "activity_classification": "requires_original_service_context_review"}


def measure_boundary(root, source):
    geometry = json.loads(_required(root, "original-attempt/map-geometry.json").read_text())
    return {"minimum_halt_body_gap_m": source["measurement"]["minimum_halt_body_gap_m"],
            "maximum_halt_body_gap_m": source["measurement"]["maximum_halt_body_gap_m"],
            "boundary_source_sha256": hashlib.sha256(_required(root, "original-attempt/map-geometry.json").read_bytes()).hexdigest(),
            "intersection_boundary_local_m": geometry["intersection_boundary_local_m"]}


def measure_traffic(root, source):
    rows = _rows(root, "original-attempt/context.jsonl")
    return {"observed_participant_count_by_frame": [len(r["participants"]) for r in rows],
            "necessity_judgment": "unresolved_from_original_traffic_geometry"}


def measure_police(root, source):
    rows = _rows(root, "original-attempt/context.jsonl")
    return {"source_frame_count": len(rows),
            "police_direction_source_state": [r.get("police_direction_judgment", "unresolved") for r in rows],
            "direction_applicability": "requires_original_direction_review"}


def measure_device(root, source):
    rows = _rows(root, "original-attempt/context.jsonl")
    return {"observed_device_count_by_frame": [len(r["directions"]) for r in rows],
            "direction_applicability": "requires_original_device_review"}


def finalize(root, case_id):
    root = Path(root)
    for relative in SOURCES:
        _required(root, relative)
    source = audit(root / "original-attempt/attempt.json",
                   allow_diagnostic=json.loads((root / "acquisition-provenance.json").read_text()).get("diagnostic_fixture") is True)
    if source["case_id"] != case_id:
        raise ValueError("Selected case identity differs")
    methods = (measure_activity, measure_boundary, measure_traffic, measure_police, measure_device)
    names = ("observed_activity", "observed_intersection_gap", "observed_traffic",
             "observed_police_direction", "observed_device_direction")
    inputs = ((SOURCES[0], SOURCES[1]), (SOURCES[0], SOURCES[2]),
              (SOURCES[0], SOURCES[3]), (SOURCES[0], SOURCES[3]), (SOURCES[0], SOURCES[3]))
    measurements = {}
    for name, method, required in zip(names, methods, inputs):
        values = {item: hashlib.sha256(_required(root, item).read_bytes()).hexdigest() for item in required}
        measurements[name] = {"method": method.__name__, "value": method(root, source),
                              "sources": values}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": measurements, "legal_necessity": "unresolved",
            "analysis_complete": True, "limitations": [
                "Traffic necessity, law compliance, police or device applicability and parking are unresolved"]}


def write_recording_channels(root, description):
    """Project original samples into the frozen eight channel/context references."""
    root = Path(root)
    pose = _rows(root, "original-attempt/pose.jsonl")
    contexts = _rows(root, "original-attempt/context.jsonl")
    if len(pose) != 900 or len(contexts) != 900:
        raise ValueError("Original channel source needs 900 joined samples")
    channels = root / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        rows = []
        for p, context in zip(pose, contexts):
            if p["world_frame"] != context["world_frame"] or p["frame"] != context["frame"]:
                raise ValueError("Original channel frame join differs")
            value = {
                "original_body_to_intersection_gap": p["observed_front_gap_m"],
                "halt_activity": {"halt_state": p["halt_state"], "speed_mps": p["speed_mps"],
                                  "requested_brake": p["requested_brake"]},
                "exception_context": {"participants": context["participants"],
                                      "directions": context["directions"],
                                      "necessity_judgment": context.get("necessity_judgment", "unresolved")},
                "traffic_conflict_history": {"participants": context["participants"]},
                "applicable_law_context": {"legal_necessity": "unresolved",
                                           "observed_frame": context["world_frame"]},
                "governing_direction_history": {"directions": context["directions"],
                                                "police_direction_judgment": context.get("police_direction_judgment", "unresolved")},
            }[name]
            rows.append({"time_s": p["time_s"], "value": value})
        relative = "channels/" + name + ".jsonl"
        (root / relative).write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    source_map = json.loads(_required(root, "original-attempt/map-geometry.json").read_text())
    measurement = json.loads(_required(root, "original-attempt/measurement.json").read_text())
    values = {"reviewed_intersection_boundary": source_map["intersection_boundary_local_m"],
              "reviewed_actor_dimensions": {"vehicle_length_m": measurement["vehicle_length_m"],
                                            "vehicle_width_m": measurement["vehicle_width_m"]}}
    for channel in description["context_inputs"]:
        name = channel["name"]
        relative = "channels/" + name + ".json"
        (root / relative).write_text(json.dumps({name: values[name]}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(_required(args.attempt, "config.json").read_text())
    report = finalize(args.attempt, config["selected_case_id"])
    from worker_exchange.native_output import physical_result, validate_result
    observed_ft = report["measurements"]["observed_intersection_gap"]["value"]["minimum_halt_body_gap_m"] / 0.3048
    evidence = write_recording_channels(args.attempt, config["recording_description"])
    result = physical_result(args.attempt, {
        "case_id": config["selected_case_id"],
        "measured_values": {key: item["value"] for key, item in report["measurements"].items()},
        "target_checks": [{"target": "requested_front_body_gap_ft", "requested": config["requested_front_body_gap_ft"],
                           "measured": observed_ft,
                           "method": "original halt body-to-boundary measurement", "tolerance": 0.5,
                           "matched": abs(observed_ft - config["requested_front_body_gap_ft"]) <= 0.5,
                           "physical_cause_confirmed": False,
                           "cause_evidence": "Original exception judgment unresolved"}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved source measured; legal judgment unresolved",
        "physical_failure_flags": {}, "trace_reference": "trace.jsonl",
        "video_references": ["raw.mkv"], "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": evidence, "realized_observables": {}})
    validate_result(result)
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
