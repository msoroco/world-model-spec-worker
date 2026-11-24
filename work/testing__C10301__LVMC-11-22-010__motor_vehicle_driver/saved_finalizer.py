"""Exact-case saved alley finalizer over audited original sources.

Exterior operation measurements remain observations. They do not establish a
person's interior attention or a legal conclusion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from attention_measurement import measure
from native_operation import CASE_PROFILES
from saved_delivery import audit
from measurement_contract import check as check_measurement_contract


def finalize(attempt: Path, case_id: str, allow_diagnostic: bool = False) -> dict:
    if case_id not in CASE_PROFILES:
        raise ValueError("unknown exact case")
    original = audit(attempt, case_id, require_delivery=not allow_diagnostic)
    operation = attempt / "operation.jsonl"
    measured = measure(operation, case_id)
    operation_hash = hashlib.sha256(operation.read_bytes()).hexdigest()
    if measured["source"]["sha256"] != operation_hash or original["source_sha256"]["operation"] != operation_hash:
        raise ValueError("measured operation is not the audited original source")
    if measured["frame_count"] != original["original_frames"]:
        raise ValueError("measured and audited original frame counts differ")
    result = {
        "format": "worker-alley-exact-saved-measurement-v1",
        "case_id": case_id,
        "selected_requirement": "LVMC-11-22-010",
        "source_kind": "audited_original_native_capture",
        "source_sha256": original["source_sha256"],
        "original_frames": original["original_frames"],
        "decoded_original_pngs": original["decoded_original_pngs"],
        "diagnostic_fixture": original["diagnostic_fixture"],
        "operation_measurement": measured,
        "attention_state": "unobserved",
        "legal_judgment": "unresolved",
    }
    contract = Path(__file__).resolve().parent / ("measurement-contract-" + case_id.rsplit("__", 1)[1] + ".json")
    check_measurement_contract(contract, attempt, result)
    return result


def analyze(attempt: Path, case_id: str) -> tuple[dict, dict]:
    """Rebuild current-runtime analysis outputs from a staged original capture."""
    from runtime_publication import _recording_evidence, _rows
    from worker_exchange.native_output import physical_result, validate_result

    diagnostic_video_only = ((attempt / "fixture-provenance.json").is_file()
                             and not (attempt / "capture.json").exists())
    for name in ("operation.jsonl", "trace.jsonl", "video_frames.jsonl",
                 "ego.jsonl", "context.jsonl", "camera-frame-map.jsonl"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    if diagnostic_video_only:
        marker = json.loads((attempt / "fixture-provenance.json").read_text())
        provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
        if ("CPU diagnostic only" not in marker.get("scope", "") or
                provenance.get("diagnostic_fixture") is not True or
                provenance.get("provenance_kind") != "fixture"):
            raise ValueError("Diagnostic video fixture provenance required")
        rows = _rows(attempt / "operation.jsonl")
        measured = measure(attempt / "operation.jsonl", case_id)
        if len(rows) != len(_rows(attempt / "trace.jsonl")) or len(rows) != len(_rows(attempt / "video_frames.jsonl")):
            raise ValueError("Diagnostic operation/frame source count differs")
        hashes = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                  for name in ("ego.jsonl", "context.jsonl", "operation.jsonl", "camera-frame-map.jsonl")}
        measurement = {"original_frames": len(rows), "decoded_original_pngs": 0,
                       "operation_measurement": measured, "source_sha256": hashes,
                       "attention_state": "unobserved", "legal_judgment": "unresolved"}
        capture = {"diagnostic_fixture": True,
                   "municipal_jurisdiction_source_sha256": hashes["context.jsonl"],
                   "alley_route_source_sha256": hashes["context.jsonl"],
                   "access_aisle_source_sha256": hashes["context.jsonl"],
                   "parking_designation_source_sha256": hashes["context.jsonl"]}
        diagnostic = True
    else:
        if not (attempt / "capture.json").is_file():
            raise ValueError("Missing required source: capture.json")
        capture = json.loads((attempt / "capture.json").read_text())
        diagnostic = capture.get("diagnostic_fixture") is True
        measurement = finalize(attempt, case_id, allow_diagnostic=diagnostic)
    construction = json.loads((attempt / "construction.json").read_text())
    recording = construction["recording_description"]
    if (attempt / "channels").exists():
        raise ValueError("Saved analysis channels must be rebuilt in a fresh stage")
    evidence = _recording_evidence(attempt, recording,
                                   {"operation": _rows(attempt / "operation.jsonl")}, capture)
    original = json.loads((attempt / "acquisition-provenance.json").read_text())
    if original.get("diagnostic_fixture") != diagnostic:
        raise ValueError("Original acquisition provenance differs from capture")
    result = {
        "case_id": case_id,
        "measured_values": {"operation_frames": measurement["original_frames"],
                            "attention_state": "unobserved", "legal_judgment": "unresolved"},
        "target_checks": [{"target": "source-bound alley operation", "requested": True,
                           "measured": measurement["original_frames"] == 900,
                           "method": "saved original same-frame operation join", "tolerance": 0,
                           "matched": measurement["original_frames"] == 900,
                           "physical_cause_confirmed": False,
                           "cause_evidence": measurement["source_sha256"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved original analysis; physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in
                             ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": recording, "recording_evidence": evidence,
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    validate_result(result)
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {key: {"method": "analyze", "value": measurement[key],
                  "sources": {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                              for name in names}}
                  for key, names in {
                      "operation_measurement": ["ego.jsonl", "context.jsonl", "operation.jsonl"],
                      "source_sha256": ["ego.jsonl", "context.jsonl", "operation.jsonl",
                                        "camera-frame-map.jsonl"],
                      "decoded_original_pngs": ["camera-frame-map.jsonl"],
                      "attention_state": ["operation.jsonl", "camera-frame-map.jsonl"],
                  }.items()},
              "physical_checks": result["physical_checks"],
              "realized_observables": result["realized_observables"],
              "provenance_kind": result["provenance_kind"],
              "diagnostic_fixture": result["diagnostic_fixture"],
              "limitations": ["Exterior observation does not establish interior attention or legal status."],
              "analysis_complete": True}
    return report, result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args(argv)
    if args.output.exists():
        raise ValueError("saved finalizer output already exists")
    if args.output.name == "analysis-report.json":
        case = args.case or json.loads((args.attempt / "config.json").read_text())["selected_case_id"]
        report, result = analyze(args.attempt, case)
        result_path = args.attempt / "result.json"
        if result_path.exists():
            raise ValueError("Saved analysis result already exists")
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        if not args.case:
            raise ValueError("--case is required for standalone measurement")
        result = finalize(args.attempt, args.case, args.allow_diagnostic)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
