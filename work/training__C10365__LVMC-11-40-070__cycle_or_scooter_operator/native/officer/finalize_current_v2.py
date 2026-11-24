"""Saved-only source measurement for the C10365 diagnostic primary probe.

Synthetic input stays synthetic. Original capture needs independent source review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from saved import process, read_rows
from worker_exchange.native_output import validate_result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(attempt, name):
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def measure_device_response(attempt, config):
    raw = source(attempt, "raw.jsonl")
    frames = source(attempt, "video.jsonl")
    review = source(attempt, "review.json")
    summary = process(attempt, raw, frames, review, synthetic=True)
    return {"value": {"stopped_before_device": summary["stopped"],
                      "stop_margin_m": summary["stop_margin_m"],
                      "crossed_device_station": summary["crossing_frame"] is not None,
                      "reviewed_direction": summary["officer_direction_reviewed"]},
            "method": "measure_device_response",
            "sources": {name: sha(attempt / name)
                        for name in ("raw.jsonl", "video.jsonl", "review.json")}}


def video_count(path):
    completed = subprocess.run([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames", "-of",
        "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=120)
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise ValueError("Source video decode failed: " + path.name)
    return int(completed.stdout.strip())


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Finalization output already exists")
    config = json.loads(source(attempt, "config.json").read_text())
    if config["duration_s"] * config["rate_hz"] != 600:
        raise ValueError("Exact duration changed")
    trace = read_rows(source(attempt, "trace.jsonl"))
    mapped = read_rows(source(attempt, "video_frames.jsonl"))
    evidence = read_rows(source(attempt, "capture/evidence.jsonl"))
    raw = read_rows(source(attempt, "raw.jsonl"))
    if not all(len(rows) == 600 for rows in (trace, mapped, evidence, raw)):
        raise ValueError("600 retained source frames required")
    for i, (t, m, e, r) in enumerate(zip(trace, mapped, evidence, raw)):
        if (m["video_frame"] != i or m["native_frame"] != r["native_frame"] or
                t["frame"] != e["original_frame"] or t["frame"] != m["native_frame"] or
                abs(t["time_s"] - m["time_s"]) > 1e-6 or
                abs(e["recording_time_s"] - m["time_s"]) > 1e-6):
            raise ValueError("Retained Native/trace/camera frame join changed")
    if not json.loads(source(attempt, "capture/manifest.json").read_text()).get("synthetic_diagnostic"):
        raise ValueError("Current probe requires explicit synthetic provenance")
    measurement = measure_device_response(attempt, config)
    channels = attempt / "channels"
    if channels.exists():
        raise ValueError("Fixture supplied derived channels")
    channels.mkdir()
    (channels / "kin.speed.jsonl").write_text("".join(
        json.dumps({"time_s": r["time_s"], "value": r["rider"]["speed_mps"]},
                   allow_nan=False) + "\n" for r in raw))
    cameras = ["overview", "approach", "reference_corner", "driver_reference"]
    for name in cameras:
        if video_count(source(attempt, name + ".mkv")) != 600:
            raise ValueError("Source camera frame count changed: " + name)
    description = config["recording_description"]
    result = {
        "case_id": config["case_id"],
        "measured_values": {"device_response": measurement["value"]},
        "target_checks": [{"target": "synthetic device response", "requested": "stop before device",
                           "measured": measurement["value"], "method": "source joined saved measurement",
                           "tolerance": "none; diagnostic classification only",
                           "matched": measurement["value"]["stopped_before_device"],
                           "physical_cause_confirmed": False,
                           "cause_evidence": list(measurement["sources"])}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "synthetic 600-frame diagnostic fixture processed",
        "physical_failure_flags": ["synthetic_fixture_not_physical",
                                   "officer_authority_and_device_applicability_unverified"],
        "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in cameras],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": [{"name": "kin.speed", "unit": "m/s",
                                "reference": "channels/kin.speed.jsonl"}],
        "realized_observables": {"stop_margin_m": {
            "value": measurement["value"]["stop_margin_m"], "unit": "m",
            "method": "source joined saved measurement", "reference": "raw.jsonl",
            "time_window": "entire 30-second diagnostic", "statistic": "minimum"}},
        "provenance_kind": "synthetic_cpu_fixture", "accepted": False,
        "legal_verdict_claimed": False}
    validate_result(result)
    report = {"format": "c10365-current-v2-analysis-v1",
              "case_id": config["case_id"], "measurements": {"device_response": measurement},
              "source_join_frames": 600, "synthetic_diagnostic": True,
              "physical_legal_verdict": None}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
