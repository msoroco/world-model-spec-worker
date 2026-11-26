"""Saved-only exact entry-timing finalizer, with explicit diagnostic separation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from entry_timing import measure


def required(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ValueError("Missing required source: " + relative)
    return path


def build(attempt: Path):
    config = json.loads(required(attempt, "config.json").read_text())
    construction = json.loads(required(attempt, "construction.json").read_text())
    case = config["selected_case_id"]
    if construction["case_id"] != case:
        raise ValueError("exact timing construction mismatch")
    source = required(attempt, "original-attempt/entry-timing-source.json")
    packet = json.loads(source.read_text())
    diagnostic = packet.get("diagnostic_fixture") is True
    if packet.get("case_id") != case:
        raise ValueError("exact timing source case mismatch")
    expected = 9 if diagnostic else 900
    if diagnostic and packet.get("source_kind") != "synthetic_fixture":
        raise ValueError("diagnostic source provenance absent")
    if not diagnostic and packet.get("source_kind") != "original_native":
        raise ValueError("original Native source provenance absent")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    measurement = measure(source, digest, case_id=case, expected_frames=expected)
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        required(attempt, name + ".mkv")
    trace = required(attempt, "trace.jsonl")
    mapping = required(attempt, "video_frames.jsonl")
    if len(trace.read_text().splitlines()) != len(mapping.read_text().splitlines()):
        raise ValueError("trace/video frame join missing")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    entry_time = measurement["entry_brackets"]["ego"]["time_bracket_s"][1]
    (channels / "entry_timing.jsonl").write_text(json.dumps({
        "time_s": entry_time,
        "value": measurement["intersection_entry_time_difference_s"]}, sort_keys=True) + "\n")
    (channels / "context.json").write_text(json.dumps({
        "reviewed_median_opening_site": {
            "source_sha256": digest,
            "review_status": "synthetic fixture" if diagnostic else "pending independent original review"}},
        sort_keys=True) + "\n")
    source_hashes = {"original-attempt/entry-timing-source.json": digest}
    report = {"format": "worker-analysis-report", "case_id": case,
              "analysis_complete": True, "legal_verdict_claimed": False,
              "measurements": {"intersection_entry_time_difference": {
                  "value": measurement, "method": "build", "sources": source_hashes}},
              "limitations": ["Approximate timing, priority and statutory exceptions require independent original review."]}
    result = {"case_id": case, "measured_values": measurement,
              "target_checks": [{"target": "original crossing entry timing",
                                 "requested": config["case"]["timing_target_s"],
                                 "measured": measurement,
                                 "method": "build", "tolerance": None,
                                 "matched": False, "physical_cause_confirmed": False,
                                 "cause_evidence": source_hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "physical and legal review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": [{"name": "intersection_entry_time_difference", "unit": "s",
                                      "reference": "channels/entry_timing.jsonl"},
                                     {"name": "reviewed_median_opening_site", "unit": "source record",
                                      "reference": "channels/context.json"}],
              "realized_observables": {},
              "provenance_kind": "synthetic_fixture" if diagnostic else "native",
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False}
    return report, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite timing report")
    report, result = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
