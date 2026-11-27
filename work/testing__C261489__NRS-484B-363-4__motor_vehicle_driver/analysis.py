"""Selected saved-only school pass measurement; never resolves statutory meaning."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_finalizer import finalize
from school_pass import ASSIGNMENT, case_name, validate_scene
from school_timing import derive as derive_timing


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_pass_activation(scene: dict, measured: dict) -> dict:
    return {"same_direction_vehicles": scene["same_direction"],
            "pass_requested": scene["pass_requested"],
            "completed_pass_original": measured.get("completed_pass"),
            "pass_inside_zone_original": measured.get("pass_inside_zone")}


def measure_calendar_session(scene: dict, measured: dict) -> dict:
    timing = derive_timing(scene["timing_packet"])
    return {"school_in_session_source": timing["school_in_session"],
            "calendar_source_sha256": scene["school_calendar_source_sha256"]}


def measure_operation_window(scene: dict, measured: dict) -> dict:
    timing = derive_timing(scene["timing_packet"])
    return {"after_end_minutes": timing["after_end_minutes"],
            "before_start_minutes": timing["before_start_minutes"],
            "half_hour_boundary": timing["half_hour_boundary"],
            "between_operation_interior": timing["between_operation_interior"]}


def measure_beacon_class(scene: dict, measured: dict) -> dict:
    timing = derive_timing(scene["timing_packet"])
    return {"during_pupil_class_hours": timing["during_pupil_class_hours"],
            "operational_beacon_designation": timing["zone_designated_by_operational_beacon"],
            "yellow_light_count": timing["beacon_yellow_light_count"],
            "alternating_flash_observed": timing["alternating_flash_observed"]}


def measure_sign_only(scene: dict, measured: dict) -> dict:
    timing = derive_timing(scene["timing_packet"])
    return {"operational_beacon_designation": timing["zone_designated_by_operational_beacon"],
            "sign_limit_active": timing["sign_limit_active"],
            "sign_source_sha256": scene["sign_instruction_source_sha256"]}


METHODS = (measure_pass_activation, measure_calendar_session, measure_operation_window,
           measure_beacon_class, measure_sign_only)
KEYS = ("pass_activation", "calendar_session", "operation_window",
        "beacon_class", "sign_only")


def analyze(attempt: Path, output: Path) -> dict:
    attempt = Path(attempt)
    config = json.loads(required(attempt, "config.json").read_text())
    construction = json.loads(required(attempt, "construction.json").read_text())
    case_id = config["selected_case_id"]
    case_name(case_id)
    if config.get("assignment_id") != ASSIGNMENT or construction.get("case_id") != case_id:
        raise ValueError("selected school-pass construction differs")
    paths = {name: required(attempt, name) for name in SOURCES}
    hashes = {name: sha(path) for name, path in paths.items()}
    scene = json.loads(paths["context.json"].read_text())
    validate_scene(scene, case_id)
    receipt = json.loads(paths["receipt.json"].read_text())
    fixture = (attempt / "fixture-provenance.json").is_file()
    source_rows = None
    if fixture:
        provenance = json.loads(required(attempt, "fixture-provenance.json").read_text())
        if (provenance.get("diagnostic_fixture") is not True or
                receipt.get("source_kind") != "synthetic_diagnostic_fixture" or
                receipt.get("assignment_id") != ASSIGNMENT or
                receipt.get("case_id") != case_id or
                receipt.get("context_sha256") != hashes["context.json"] or
                receipt.get("trace_sha256") != hashes["original-trace.jsonl"] or
                receipt.get("camera_manifest_sha256") != hashes["cameras.json"]):
            raise ValueError("synthetic school-pass fixture source seal mismatch")
        source_rows = [json.loads(line) for line in paths["original-trace.jsonl"].read_text().splitlines()]
        if len(source_rows) != provenance.get("frames") or not source_rows:
            raise ValueError("bounded diagnostic original school trace incomplete")
        measured = {"diagnostic_frames": len(source_rows), "physical_pass": "unverified"}
    else:
        measured = finalize(case_id, paths["context.json"], paths["original-trace.jsonl"],
                            paths["receipt.json"], paths["cameras.json"])
    trace = [json.loads(line) for line in required(attempt, "trace.jsonl").read_text().splitlines()]
    if len(trace) != (measured["diagnostic_frames"] if fixture else 900):
        raise ValueError("Core trace and selected school-pass source count differ")
    if fixture and any(
        row.get("frame") != source.get("original_frame") or
        abs(row.get("time_s", -1000) - source.get("time_s", 1000)) > .002
        for row, source in zip(trace, source_rows)
    ):
        raise ValueError("Core and selected diagnostic school-pass frame/time join differs")
    measurement = {
        key: {"method": method.__name__, "value": method(scene, measured), "sources": hashes}
        for key, method in zip(KEYS, METHODS)
    }
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": measurement, "diagnostic_fixture": fixture,
              "legal_verdict_claimed": False,
              "limitations": ["Original pass, zone, device and legal exception application require independent review.",
                              "Synthetic diagnostic frames do not establish physical passing or lamp visibility."]}
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        relative = "channels/" + name + ".jsonl"
        with (attempt / relative).open("x") as stream:
            for row in trace:
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "value": {"case_id": case_id, "source_hashes": hashes,
                                                   "selected_measurements": measurement}}, sort_keys=True) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    context_relative = "channels/reviewed_original_school_sources.json"
    (attempt / context_relative).write_text(json.dumps({"reviewed_original_school_sources": {
        "context_sha256": hashes["context.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_original_school_sources", "unit": "source",
                     "reference": context_relative})
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "source-bound same-direction school-zone passing",
                                 "requested": case_id, "measured": measured,
                                 "method": "school_pass.measure_original", "tolerance": 0,
                                 "matched": True, "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": bool(measured.get("completed_pass", False)),
              "termination_reason": "Original school-pass physical/source review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS] + ["raw.mkv"],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "legal_judgment": None, "physical_acceptance_claimed": False}
    (attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)["case_id"])


if __name__ == "__main__":
    main()
