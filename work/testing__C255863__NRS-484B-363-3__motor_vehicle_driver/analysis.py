"""Selected saved school-zone measurement without a legal or physical verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_finalizer import finalize
from school_scene_construction import ASSIGNMENT, load_case


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text())
    construction = json.loads(required(root, "construction.json").read_text())
    case_id = config["selected_case_id"]
    case = load_case(case_id)
    if construction["case_id"] != case_id or case_id not in config["supported_case_ids"]:
        raise ValueError("selected school-zone construction differs")
    paths = {name: required(root, name) for name in
             ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")}
    context = json.loads(paths["context.json"].read_text())
    fixture = (root / "fixture-provenance.json").is_file()
    if fixture:
        provenance = json.loads(required(root, "fixture-provenance.json").read_text())
        receipt = json.loads(paths["receipt.json"].read_text())
        if (provenance.get("diagnostic_fixture") is not True or
                receipt.get("source_kind") != "synthetic_diagnostic_fixture" or
                receipt.get("assignment_id") != ASSIGNMENT or
                receipt.get("case_id") != case_id or
                receipt.get("context_sha256") != sha(paths["context.json"]) or
                receipt.get("trace_sha256") != sha(paths["original-trace.jsonl"]) or
                receipt.get("camera_manifest_sha256") != sha(paths["cameras.json"])):
            raise ValueError("synthetic fixture source seal mismatch")
        rows = [json.loads(line) for line in paths["original-trace.jsonl"].read_text().splitlines()]
        if len(rows) != 9 or context.get("case_id") != case_id:
            raise ValueError("bounded diagnostic school trace incomplete")
        for field in ("children_present", "school_session", "operation_window",
                      "beacon_operational", "beacon_flashing", "sign_limit_active"):
            if context.get(field) is not getattr(case, field):
                raise ValueError("diagnostic intervention differs: " + field)
        for i, row in enumerate(rows):
            if row.get("frame") != i or abs(row.get("time_s", -100) - i / 20) > .002:
                raise ValueError("bounded diagnostic school cadence mismatch")
        measurement = {"diagnostic_frames": 9, "physical_reversal": "unverified"}
    else:
        measurement = finalize(case_id, *paths.values())
    values = {"original_frame_count": 9 if fixture else 900,
              "children_present_source_label": context.get("children_present"),
              "school_session_source_label": context.get("school_session"),
              "operation_window_source_label": context.get("operation_window"),
              "beacon_operational_source_label": context.get("beacon_operational"),
              "beacon_flashing_source_label": context.get("beacon_flashing"),
              "sign_limit_active_source_label": context.get("sign_limit_active"),
              "measured_reversal": measurement,
              "uturn_legal_judgment": "unresolved",
              "children_presence_judgment": "unresolved"}
    hashes = {name: sha(path) for name, path in paths.items()}
    return case_id, values, hashes, fixture, construction


def analyze(attempt, output):
    root = Path(attempt)
    case_id, values, hashes, fixture, construction = measure(root)
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != values["original_frame_count"]:
        raise ValueError("Core trace and selected school history count differ")
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"school_zone_uturn_context": {
                  "method": "measure", "value": values, "sources": hashes}},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["School designation, child presence and exception legality need original review.",
                              "Diagnostic frames do not establish physical U-turn success."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        target = channels / (name + ".jsonl")
        source_hash = hashes["cameras.json"] if name == "original_four_camera_pixels" else hashes["original-trace.jsonl"]
        with target.open("x") as stream:
            for row in trace:
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "value": {"source_sha256": source_hash,
                                                   "case_id": case_id,
                                                   "measurement": values}}, sort_keys=True) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context_target = channels / "reviewed_original_school_sources.json"
    context_target.write_text(json.dumps({"reviewed_original_school_sources": {
        "source_sha256": hashes["context.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_original_school_sources", "unit": "source",
                     "reference": str(context_target.relative_to(root))})
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [{"target": "source-bound school crossing-zone U-turn context",
                                 "requested": case_id, "measured": values,
                                 "method": "school_uturn.measure_original",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Original school-source and physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "legal_judgment": None, "physical_acceptance_claimed": False}
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)["case_id"])


if __name__ == "__main__":
    main()
