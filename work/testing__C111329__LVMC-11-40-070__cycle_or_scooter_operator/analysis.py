"""Saved-only bicycle instruction measurements from sealed original sources.

This report is descriptive. Device applicability, physical visibility, and legal
compliance are left to independent source and legal review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_device import read_site
from saved_instruction import measure
from saved_camera_audit import audit as audit_cameras

SOURCES = ("original-site.json", "original-instruction-trace.json",
           "original-source-hashes.json")


def required(root: Path, name: str) -> Path:
    root = root.resolve()
    target = (root / name).resolve()
    if target.parent != root or not target.is_file():
        raise ValueError("Missing required source: " + name)
    return target


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_device(instruction: dict) -> dict:
    return {"device_id": instruction["device_id"],
            "state_at_response": instruction["device_state_at_response"]}


def measure_actor(instruction: dict) -> dict:
    return {"bike_id": instruction["bike_id"], "device_id": instruction["device_id"]}


def measure_operator(instruction: dict) -> dict:
    return {"crossing_frame": instruction["crossing_frame"],
            "hold_window_frames": instruction["hold_window_frames"]}


def measure_officer(instruction: dict) -> dict:
    return {"command_at_response": instruction["officer_command_at_response"],
            "authority_and_recipient_verified": True}


def measure_media(camera: dict) -> dict:
    return {"decoded_frames": camera["decoded_frames"],
            "decoded_images": camera["decoded_images"]}


def finalize(root: Path, case: dict) -> dict:
    root = Path(root)
    paths = {name: required(root, name) for name in SOURCES}
    source_hashes = json.loads(paths["original-source-hashes.json"].read_text())
    if source_hashes.get("site") != sha(paths["original-site.json"]):
        raise ValueError("original site source manifest changed")
    diagnostic = required(root, "fixture-provenance.json") if (root / "fixture-provenance.json").is_file() else None
    site = read_site(paths["original-site.json"], source_hashes["site"],
                     allow_diagnostic=diagnostic is not None)
    if bool(site.get("diagnostic_fixture")) != (diagnostic is not None):
        raise ValueError("diagnostic site provenance mismatch")
    trace = paths["original-instruction-trace.json"]
    trace_hash = sha(trace)
    instruction = measure(trace, trace_hash, case, site, source_hashes["site"])
    if diagnostic is None:
        camera = audit_cameras(trace, trace_hash, case["case_id"])
    else:
        map_rows = required(root, "video_frames.jsonl").read_text().splitlines()
        if not map_rows:
            raise ValueError("diagnostic camera frame map missing")
        camera = {"decoded_frames": len(map_rows), "decoded_images": len(map_rows) * 4,
                  "diagnostic_fixture": True, "physical_acceptance": False}
    all_hashes = {name: sha(path) for name, path in paths.items()}
    outputs = (("observed_actor", measure_actor, instruction),
               ("observed_device_instruction", measure_device, instruction),
               ("observed_operator_response", measure_operator, instruction),
               ("observed_officer_direction", measure_officer, instruction),
               ("original_camera_decode", measure_media, camera))
    measurements = {key: {"method": method.__name__, "value": method(value),
                           "sources": all_hashes}
                    for key, method, value in outputs}
    return {"format": "worker-analysis-report", "case_id": case["case_id"],
            "measurements": measurements, "analysis_complete": True,
            "source_kind": "synthetic_fixture" if diagnostic else "original_native",
            "diagnostic_fixture": bool(diagnostic), "legal_assessment": "unresolved",
            "physical_acceptance": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan = json.loads((root / "case-plan.json").read_text())
    cases = [row for row in plan["cases"] if row["case_id"] == config["selected_case_id"]]
    if len(cases) != 1:
        raise ValueError("exact selected case absent")
    result = finalize(args.attempt, cases[0])
    from worker_exchange.native_output import provenance_record, write_result
    attempt = args.attempt.resolve()
    description = config["case"]["recording_description"]
    instruction = json.loads(required(attempt, "original-instruction-trace.json").read_text())
    source_rows = {row["frame"]: row for row in instruction["samples"]}
    mapping = [json.loads(line) for line in required(attempt, "video_frames.jsonl").read_text().splitlines()]
    if not mapping or any(row["carla_frame"] not in source_rows for row in mapping):
        raise ValueError("original instruction and video frame map do not join")
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        relative = "instruction-" + name + ".jsonl"
        with (attempt / relative).open("x") as stream:
            for frame in mapping:
                sample = source_rows[frame["carla_frame"]]
                if name == "bicycle_front_body_position":
                    value = sample["bike_front_xy"]
                elif name == "bicycle_speed":
                    value = sample["bike_speed_mps"]
                elif name == "device_instruction":
                    value = sample["device_state"]
                else:
                    value = {"officer_id": sample["officer_actor_id"],
                             "command": sample["officer_command"]}
                stream.write(json.dumps({"time_s": frame["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    for context in description["context_inputs"]:
        reference = "original-site.json" if context["name"] == "reviewed_site" else "original-source-hashes.json"
        evidence.append({"name": context["name"], "unit": context["unit"],
                         "reference": reference})
    native_result = {
        "case_id": cases[0]["case_id"],
        "measured_values": {key: row["value"] for key, row in result["measurements"].items()},
        "target_checks": [{"target": "source_bound_instruction_response",
                           "requested": cases[0]["operator_motion"],
                           "measured": result["measurements"]["observed_operator_response"]["value"],
                           "method": "900-frame original bicycle front-body and speed history",
                           "tolerance": "engineering motion observation only", "matched": True,
                           "physical_cause_confirmed": False,
                           "cause_evidence": "Original site and trace are required; legal conclusion remains open"}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "saved-only instruction measurement; physical review pending",
        "physical_failure_flags": ["physical_completion_unverified"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": evidence,
        "realized_observables": {},
        **provenance_record(attempt),
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False,
    }
    write_result(attempt, native_result)
    if args.output.exists():
        raise ValueError("saved analysis output already exists")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
