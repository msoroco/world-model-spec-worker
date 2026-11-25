"""Source-bound saved analysis for the selected ordinary and officer-direction cases.

Synthetic CPU fixtures retain synthetic provenance. A reviewed original attempt
must carry its own Native rows, four videos, map receipt and independent review.
"""
import argparse
import hashlib
import json
from pathlib import Path

from saved import process, read_rows
from worker_exchange.native_output import validate_result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def measure_device_response(response, sources):
    return {"value": response, "method": "measure_device_response",
            "sources": sources,
            "scope": "source-bound diagnostic; legal instruction interpretation remains independent"}


def analyze(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Finalization output already exists")
    config = json.loads(source(attempt, "config.json").read_text())
    if config["duration_s"] != 30 or config["rate_hz"] != 20:
        raise ValueError("Exact four-view duration changed")
    manifest = json.loads(source(attempt, "capture/manifest.json").read_text())
    synthetic = manifest.get("synthetic_diagnostic") is True
    raw_name = "raw.jsonl" if synthetic else "native-raw-actors.jsonl"
    raw = source(attempt, raw_name)
    frames = source(attempt, "video_frames.jsonl")
    review = source(attempt, "review.json")
    trace = read_rows(source(attempt, "trace.jsonl"))
    native = read_rows(raw)
    mapped = read_rows(frames)
    evidence = read_rows(source(attempt, "capture/evidence.jsonl"))
    if not all(len(rows) == 600 for rows in (trace, native, mapped, evidence)):
        raise ValueError("600 original source joins required")
    for index, (t, r, m, e) in enumerate(zip(trace, native, mapped, evidence)):
        if (m["video_frame"] != index or r["native_frame"] != m["native_frame"] or
                t["frame"] != m["native_frame"] or e["original_frame"] != m["native_frame"] or
                abs(t["time_s"] - m["time_s"]) > 1e-6 or
                abs(e["recording_time_s"] - m["time_s"]) > 1e-6):
            raise ValueError("Saved Native/Core/video join changed")
    measured = process(attempt, raw, frames, review, synthetic=synthetic)
    channels = attempt / "channels"
    if channels.exists():
        raise ValueError("Fixture supplied derived channels")
    channels.mkdir()
    channel = channels / "kin.speed.jsonl"
    channel.write_text("".join(json.dumps({"time_s": row["time_s"],
                                           "value": row["rider"]["speed_mps"]}) + "\n"
                               for row in native))
    response = {"stopped_before_device": measured["stopped"],
                "stop_margin_m": measured["stop_margin_m"],
                "crossed_device_station": measured["crossing_frame"] is not None,
                "reviewed_direction": measured["officer_direction_reviewed"]}
    sources = {name: sha(attempt / name) for name in (raw_name, "video_frames.jsonl", "review.json")}
    physical = (measured["stopped"] if config["case_id"].endswith("probe_a")
                else measured["crossing_frame"] is not None)
    original_complete = not synthetic and physical
    map_path = attempt / "native-map-readback.json"
    map_sha = sha(map_path) if map_path.exists() else None
    fixed = {"cell_id": config["cell_id"], "law_id": config["law_id"],
             "actor": config["actor"], "road_sha256": sha(attempt / "alley-stop.xodr"),
             "device_id": "3651", "candidate_id": config["candidate_id"],
             "camera_policy": config["camera_policy"],
             "camera_sources": config["camera_sources"],
             "requested_speed_mps": config["requested_speed_mps"],
             "officer_position_xy_m": config["officer_position_xy_m"],
             "duration_s": config["duration_s"], "rate_hz": config["rate_hz"]}
    result = {
        "case_id": config["case_id"], "measured_values": {"device_response": response},
        "target_checks": [{"target": "reviewed source device response",
                           "requested": config["officer_cue_requested"],
                           "measured": response, "method": "saved original actor, frame and review joins",
                           "tolerance": "none; no legal threshold", "matched": original_complete,
                           "physical_cause_confirmed": False,
                           "cause_evidence": list(sources)}],
        "setup_confirmed": not synthetic,
        "behavior_attempted": not synthetic,
        "maneuver_completed": original_complete,
        "termination_reason": "reviewed original 600-frame attempt" if not synthetic else
                              "synthetic 600-frame diagnostic fixture",
        "physical_failure_flags": [] if original_complete else
                                  ["original_review_or_motion_unverified"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in
                             ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": "kin.speed", "unit": "m/s",
                                "reference": "channels/kin.speed.jsonl"}],
        "realized_observables": {"device_response": {
            "value": response, "unit": "categorical_and_metres",
            "method": "reviewed source actor and device measurement",
            "reference": raw_name, "time_window": "30 seconds / 600 frames",
            "statistic": "stop and crossing summary"}} if not synthetic else {},
        "physical_checks": {
            "maneuver": {"status": "met" if original_complete else "unverified",
                         "method": "600 source actor, speed and crossing samples",
                         "sources": sources},
            "setup": {"status": "met" if not synthetic else "unverified",
                      "method": "original map/landmark and independent device/officer review",
                      "sources": {"native-map-readback.json": map_sha} if map_sha else {}}},
        "comparison_fixed_conditions": fixed,
        "provenance_kind": "synthetic_fixture" if synthetic else "original_native",
        "diagnostic_fixture": synthetic, "accepted": False,
        "legal_verdict_claimed": False,
    }
    validate_result(result)
    measurement = measure_device_response(response, sources)
    report = {"format": "c10365-selected-source-analysis-v1",
              "case_id": config["case_id"], "measurements": {"device_response": measurement},
              "source_join_frames": 600, "synthetic_diagnostic": synthetic,
              "original_map_sha256": map_sha,
              "legal_outcome_claimed": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt, args.output), sort_keys=True))
