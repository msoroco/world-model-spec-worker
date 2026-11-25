"""Saved-only alley body/access measurement and Native result projection."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from access_measurement import measure
from physical_parking import assess


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify(attempt: Path, name: str) -> Path:
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def measure_alley_access(source_root: Path, inventory: dict, case_id: str) -> dict:
    return measure(source_root, inventory, case_id)


def build(attempt: Path) -> tuple[dict, dict]:
    attempt = Path(attempt).resolve()
    config = json.loads(verify(attempt, "config.json").read_text())
    source_root = attempt / "original-attempt"
    inventory = json.loads(verify(source_root, "inventory.json").read_text())
    for name in ("frame_map", "alley_geometry", "vehicle_footprint", "activity"):
        verify(attempt, "original-attempt/" + name + ".json")
    diagnostic = verify(attempt, "fixture-provenance.json") if (attempt / "fixture-provenance.json").exists() else None
    if diagnostic is not None:
        marker = json.loads(diagnostic.read_text())
        if marker.get("diagnostic_fixture") is not True or marker.get("physical_acceptance_claimed") is not False:
            raise ValueError("untrusted diagnostic alley provenance")
        if inventory.get("diagnostic_fixture") is not True:
            raise ValueError("diagnostic alley source inventory differs")
    elif inventory.get("diagnostic_fixture") is not False:
        raise ValueError("original Native alley provenance missing")
    measurement = measure_alley_access(source_root, inventory, config["selected_case_id"])
    frames = rows(verify(attempt, "video_frames.jsonl"))
    trace = rows(verify(attempt, "trace.jsonl"))
    original = json.loads(verify(source_root, "frame_map.json").read_text())["frames"]
    if (len(frames) != len(trace) or len(frames) != len(original) or
            any(row.get("video_frame") != i or row.get("carla_frame") != src["frame"] or
                row.get("time_s") != src["time_s"] or trace[i].get("frame") != src["frame"]
                for i, (row, src) in enumerate(zip(frames, original)))):
        raise ValueError("original alley trace/video/frame identity join differs")
    source_hashes = {"original-attempt/" + name + ".json": value
                     for name, value in measurement["source_sha256"].items()}
    value = {"max_access_intrusion_area_m2": measurement["max_access_intrusion_area_m2"],
             "measured_halt_frames": measurement["measured_halt_frames"],
             "access_kind": measurement["access_kind"],
             "property_id": measurement["property_id"],
             "statutory_blocking_judgment": None}
    report = {"format": "worker-analysis-report",
              "measurements": {"access_position_measurement": {
                  "value": value, "method": "measure_alley_access",
                  "sources": source_hashes}},
              "analysis_complete": True, "legal_verdict_claimed": False,
              "limitations": ["Engineering access overlap is not a legal blocking cutoff.",
                              "Original alley qualification, camera visibility and blocking need independent review."]}
    return report, measurement


def save_result(attempt: Path, report: dict, measurement: dict) -> dict:
    from worker_exchange.native_output import validate_result
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    frame_rows = rows(attempt / "video_frames.jsonl")
    source_root = attempt / "original-attempt"
    inventory = json.loads((source_root / "inventory.json").read_text())
    activity = json.loads((source_root / "activity.json").read_text())["samples"]
    overlap = {r["frame"]: r["access_intrusion_area_m2"] for r in measurement["halt_samples"]}
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    channel_values = {
        "original_body_access_overlap": [overlap.get(r["carla_frame"], 0.0) for r in frame_rows],
        "parking_activity": activity,
        "qualifying_alley_and_access": [inventory["sources"]["alley_geometry"]] * len(frame_rows)}
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for row, value in zip(frame_rows, channel_values[name]):
                stream.write(json.dumps({"time_s": row["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_path = channels / "context.json"
    context_path.write_text(json.dumps({"reviewed_alley_packet": {
        "geometry_sha256": inventory["sources"]["alley_geometry"]["sha256"],
        "map_sha256": inventory["map_sha256"],
        "review_status": "pending independent original-source review"}}) + "\n")
    for context in construction["recording_description"]["context_inputs"]:
        evidence.append({"name": context["name"], "unit": context["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    target = (measurement["max_access_intrusion_area_m2"] == 0 if
              config["parking_position"] == "clear" else
              measurement["max_access_intrusion_area_m2"] > 0)
    physical = assess(attempt, config, measurement)
    result = {"case_id": config["selected_case_id"],
              "measured_values": report["measurements"]["access_position_measurement"]["value"],
              "target_checks": [{"target": "original body position relative to abutting access",
                                 "requested": config["parking_position"],
                                 "measured": measurement["max_access_intrusion_area_m2"],
                                 "method": "measure_alley_access", "tolerance": 0,
                                 "matched": target, "physical_cause_confirmed": False,
                                 "cause_evidence": measurement["source_sha256"]}],
              "setup_confirmed": physical["setup_confirmed"],
              "behavior_attempted": physical["behavior_attempted"],
              "maneuver_completed": physical["maneuver_completed"],
              "termination_reason": "Saved original access evidence awaits independent physical and legal review",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence,
              "realized_observables": physical["realized_observables"],
              "physical_checks": physical["physical_checks"],
              "provenance_kind": "synthetic_fixture" if inventory["diagnostic_fixture"] else "native",
              "diagnostic_fixture": inventory["diagnostic_fixture"],
              "physical_acceptance_claimed": False}
    validate_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    attempt = args.attempt.resolve()
    report, measurement = build(attempt)
    result = save_result(attempt, report, measurement)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    if (attempt / "result.json").exists() or args.output.exists():
        raise ValueError("refusing to replace saved original alley analysis")
    (attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
