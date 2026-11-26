"""Saved-only posted-speed finalizer; diagnostic and original sources stay distinct."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ValueError("Missing required source: " + relative)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(attempt: Path) -> tuple[dict, dict]:
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, "config.json").read_text())
    construction = json.loads(required(attempt, "construction.json").read_text())
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("selected posted-speed construction changed")
    specific = required(attempt, "original-attempt/posted-speed-source.json")
    packet = json.loads(specific.read_text())
    diagnostic = packet.get("diagnostic_fixture") is True
    if packet.get("case_id") != case_id:
        raise ValueError("posted-speed finalizer exact case mismatch")
    if diagnostic:
        if packet.get("source_kind") != "synthetic_fixture" or not isinstance(packet.get("samples"), list) or len(packet["samples"]) != 9:
            raise ValueError("diagnostic posted-speed sample contract invalid")
        measurement = {"diagnostic_samples": packet["samples"],
                       "source_kind": "synthetic_fixture",
                       "legal_applicability": "unresolved"}
    else:
        from original_source_audit import audit as audit_original
        from speed_source_review import measure as measure_original
        inventory = json.loads(required(attempt, "original-attempt/inventory.json").read_text())
        source_receipt = audit_original(attempt / "original-attempt", inventory, case_id)
        measurement = measure_original(attempt / "original-attempt", inventory, case_id)
        measurement["source_audit"] = source_receipt
    traces = [json.loads(line) for line in required(attempt, "trace.jsonl").read_text().splitlines() if line]
    mapping = [json.loads(line) for line in required(attempt, "video_frames.jsonl").read_text().splitlines() if line]
    if not traces or len(traces) != len(mapping):
        raise ValueError("posted-speed trace/video frame join incomplete")
    for name in VIEWS:
        required(attempt, name + ".mkv")
    channels = attempt / "channels"
    if channels.exists():
        raise ValueError("refusing to overwrite original speed channels")
    channels.mkdir()
    path = channels / "actual_speed_mps.jsonl"
    rows = packet["samples"] if diagnostic else measurement["samples"]
    path.write_text("".join(json.dumps({"time_s": row.get("time_s"),
                                        "value": row["speed_mps"]}, sort_keys=True) + "\n"
                            for row in rows))
    context = channels / "context.json"
    context.write_text(json.dumps({"reviewed_posted_site": {
        "sha256": sha(specific),
        "review_status": "synthetic fixture" if diagnostic else "pending independent original review"}},
        sort_keys=True) + "\n")
    sources = {"original-attempt/posted-speed-source.json": sha(specific)}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "analysis_complete": True, "legal_verdict_claimed": False,
              "measurements": {"posted_speed_history": {"value": measurement,
                                                     "method": "build", "sources": sources}},
              "limitations": ["Original posted authority, actual capture and legal applicability require independent review."]}
    result = {"case_id": case_id, "measured_values": measurement,
              "target_checks": [{"target": "original posted-speed passage",
                                 "requested": config["case"]["draft_variables"],
                                 "measured": measurement, "method": "build",
                                 "tolerance": None, "matched": False,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": sources}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "original physical and legal review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": [{"name": "actual_speed_mps", "unit": "m/s",
                                      "reference": "channels/actual_speed_mps.jsonl"},
                                     {"name": "reviewed_posted_site", "unit": "source record",
                                      "reference": "channels/context.json"}],
              "realized_observables": {},
              "provenance_kind": "synthetic_fixture" if diagnostic else "native",
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False}
    return report, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite posted-speed analysis report")
    report, result = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
