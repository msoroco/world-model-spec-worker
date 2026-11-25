"""Saved-only rail-stop measurements from original Native sources.

The finalizer reports distance, cessation, departure and conflict observations.
It never assigns a legal vehicle reference point or due-care verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rail_stop_audit import audit_saved_file


def _sha(path: Path) -> str:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_crossing_authority(packet: dict, source_hashes: dict) -> dict:
    return {"method": "measure_crossing_authority",
            "sources": {name: source_hashes[name] for name in
                        ("rail-stop-packet.json", "native-authority-record.json", "native-stop-device.json",
                         "native-crossing-geometry.json")},
            "value": {"crossing_type": packet["context"]["crossing_type"],
                      "designation_authority": packet["context"]["designation_authority"],
                      "device_type": packet["context"]["device_type"],
                      "device_governs": packet["context"]["device_governs"],
                      "legal_source_review": "pending"}}


def measure_stop_gap(measurement: dict, source_hashes: dict) -> dict:
    return {"method": "measure_stop_gap",
            "sources": {name: source_hashes[name] for name in
                        ("rail-stop-packet.json", "native-crossing-geometry.json", "native-ego-footprint.json",
                         "native-ego-kinematics.json")},
            "value": {"complete_stop_observed": measurement["complete_stop_observed"],
                      "minimum_body_corner_gap_ft": measurement.get(
                          "first_stop_body_to_nearest_rail_min_ft"),
                      "body_signed_range_ft": measurement.get("first_stop_body_signed_range_ft"),
                      "vehicle_reference_point": "unresolved"}}


def measure_cessation(measurement: dict, source_hashes: dict) -> dict:
    return {"method": "measure_cessation",
            "sources": {name: source_hashes[name] for name in
                        ("rail-stop-packet.json", "native-ego-kinematics.json")},
            "value": {"complete_stop_observed": measurement["complete_stop_observed"],
                      "stop_samples": measurement["stop_samples"],
                      "first_stop_frame": measurement.get("first_stop_frame")}}


def measure_departure_context(measurement: dict, source_hashes: dict) -> dict:
    return {"method": "measure_departure_context",
            "sources": {"rail-stop-packet.json": source_hashes["rail-stop-packet.json"]},
            "value": {"proceeding_observed": measurement["proceeding_observed"],
                      "conflict_actor_present": measurement["conflict_actor_present"],
                      "minimum_departure_conflict_body_separation_m": measurement.get(
                          "minimum_departure_conflict_body_separation_m"),
                      "due_care": "unresolved by physical measurement alone"}}


def analyze(attempt: Path, output: Path) -> dict:
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.parent != attempt:
        raise ValueError("saved analysis report must stay in its original attempt")
    config = json.loads((attempt / "config.json").read_text())
    case = config["case"]
    if case["case_id"] != config["selected_case_id"]:
        raise ValueError("saved exact case identity differs")
    packet_path = attempt / "rail-stop-packet.json"
    _sha(packet_path)
    packet = json.loads(packet_path.read_text())
    measurement = audit_saved_file(packet_path)
    mapping = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    samples = packet["samples"]
    expected_frames = config["duration_s"] * config["rate_hz"]
    if (expected_frames != 900 or len(mapping) != expected_frames or
            len(trace) != expected_frames or len(samples) != expected_frames):
        raise ValueError("complete 900-frame original capture required")
    for index, (mapped, frame, sample) in enumerate(zip(mapping, trace, samples)):
        if (mapped.get("video_frame") != index or
                mapped.get("carla_frame") != sample.get("source_frame") or
                frame.get("frame") != sample.get("source_frame") or
                frame.get("time_s") != mapped.get("time_s") or
                mapped.get("native_frame") != sample.get("source_frame")):
            raise ValueError("original video, trace and rail packet frame join differs")
    selected_conflict = case["departure_context"] == "crossing_conflict"
    if measurement["conflict_actor_present"] != selected_conflict:
        raise ValueError("selected crossing-conflict actor differs from original")
    stop_observed = measurement["complete_stop_observed"]
    desired_stop = case["stop_behavior"] == "complete"
    gap = measurement.get("first_stop_body_to_nearest_rail_min_ft",
                          measurement.get("minimum_body_to_nearest_rail_min_ft"))
    # The tolerance is a construction feedback threshold in feet. It cannot
    # resolve the statute's unspecified vehicle reference point.
    target_checks = [
        {"target": "complete_cessation", "requested": desired_stop,
         "measured": stop_observed, "method": "saved 20 Hz original ego speed after approach",
         "tolerance": 0, "matched": desired_stop == stop_observed,
         "physical_cause_confirmed": False,
         "cause_evidence": {"rail_packet_sha256": _sha(packet_path),
                            "independent_review": "pending"}},
        {"target": "commanded_body_gap_ft", "requested": case["planned_stop_body_gap_ft"],
         "measured": gap, "method": "original four-corner body interval to nearest rail line",
         "tolerance": 0.5,
         "matched": gap is not None and abs(gap - case["planned_stop_body_gap_ft"]) <= 0.5,
         "physical_cause_confirmed": False,
         "cause_evidence": {"rail_packet_sha256": _sha(packet_path),
                            "legal_reference_point": "unresolved"}}]
    sources = {name: _sha(attempt / name) for name in
               ("rail-stop-packet.json", "trace.jsonl", "video_frames.jsonl",
                "native-crossing-geometry.json", "native-authority-record.json",
                "native-stop-device.json", "native-ego-kinematics.json",
                "native-ego-footprint.json")}
    if selected_conflict:
        sources["native-conflict-history.json"] = _sha(attempt / "native-conflict-history.json")
    report = {"format": "worker-analysis-report", "analysis_complete": True,
              "measurements": {
                  "crossing_authority": measure_crossing_authority(packet, sources),
                  "stop_gap": measure_stop_gap(measurement, sources),
                  "cessation": measure_cessation(measurement, sources),
                  "departure_context": measure_departure_context(measurement, sources)},
              "limitations": ["Statutory vehicle reference point and due care require independent original scene review."],
              "legal_verdict_claimed": False}
    if output.exists():
        raise ValueError("retain prior saved rail analysis")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    channel_path = channels / "rail_stop.jsonl"
    with channel_path.open("x") as stream:
        for frame, sample in zip(mapping, samples):
            stream.write(json.dumps({"time_s": frame["time_s"],
                                     "value": {"speed_mps": sample["speed_mps"],
                                               "body_corners_xy_m": sample["body_corners_xy_m"],
                                               "original_frame": sample["source_frame"]}},
                                    allow_nan=False) + "\n")
    conflict_path = channels / "crossing_conflict_history.jsonl"
    with conflict_path.open("x") as stream:
        for index, frame in enumerate(mapping):
            actor = packet.get("conflict_samples")
            value = ({"actor_present": True,
                      "body_corners_xy_m": actor[index]["body_corners_xy_m"],
                      "speed_mps": actor[index]["speed_mps"],
                      "original_frame": actor[index]["source_frame"]}
                     if actor is not None else {"actor_present": False,
                                                 "original_frame": frame["carla_frame"]})
            stream.write(json.dumps({"time_s": frame["time_s"], "value": value},
                                    allow_nan=False) + "\n")
    context_path = channels / "context.json"
    context_path.write_text(json.dumps({"crossing_authority": {
        "authority_source_sha256": sources["native-authority-record.json"],
        "stop_device_source_sha256": sources["native-stop-device.json"],
        "rail_geometry_source_sha256": sources["native-crossing-geometry.json"],
        "site_review_pending": True}}, indent=2) + "\n")
    result = {"case_id": case["case_id"], "measured_values": report["measurements"],
              "target_checks": target_checks, "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original sources measured; physical and legal review pending",
              "physical_failure_flags": {"physical_review_pending": True},
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": [
                  {"name": "rail_stop", "unit": "structured", "reference": "channels/rail_stop.jsonl"},
                  {"name": "crossing_conflict_history", "unit": "structured",
                   "reference": "channels/crossing_conflict_history.jsonl"},
                  {"name": "crossing_authority", "unit": "metadata", "reference": "channels/context.json"}],
              "realized_observables": {}, "legal_judgment": "unresolved",
              "source_sha256": sources}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    result_path = attempt / "result.json"
    if result_path.exists():
        raise ValueError("retain prior saved result")
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
