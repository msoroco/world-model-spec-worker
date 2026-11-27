"""Selected saved heavy-vehicle measurements; no inferred legal or physical verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

from saved_finalizer import finalize
from crossing_scene import ASSIGNMENT, load_case

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_NAMES = ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def diagnostic_measure(case, context, rows, receipt, paths):
    if (receipt.get("source_kind") != "synthetic_diagnostic_fixture" or
            receipt.get("diagnostic_fixture") is not True or
            receipt.get("assignment_id") != ASSIGNMENT or
            receipt.get("case_id") != case["case_id"] or
            receipt.get("context_sha256") != sha(paths["context.json"]) or
            receipt.get("trace_sha256") != sha(paths["original-trace.jsonl"]) or
            receipt.get("camera_manifest_sha256") != sha(paths["cameras.json"])):
        raise ValueError("diagnostic heavy-vehicle source seal mismatch")
    if len(rows) < 3 or len(rows) > 900 or context.get("case_id") != case["case_id"]:
        raise ValueError("bounded diagnostic heavy-vehicle trace incomplete")
    speeds = []
    for index, row in enumerate(rows):
        speed = row.get("heavy_speed_mps")
        if (row.get("frame") != index or
                type(row.get("time_s")) not in (int, float) or
                abs(row["time_s"] - index / 20) > .002 or
                type(speed) not in (int, float) or
                not math.isfinite(speed) or speed < 0 or
                type(row.get("inside_designated_zone")) is not bool or
                type(row.get("sign_limit_active")) is not bool or
                not isinstance(row.get("beacon_yellow_lights_lit"), list) or
                any(type(x) is not bool for x in row["beacon_yellow_lights_lit"])):
            raise ValueError("diagnostic heavy-vehicle frame readback incomplete")
        speeds.append(speed * 2.2369362921)
    for field, expected in (("school_in_session_today", case["session_request"] == "session"),
                            ("time_window_label", case["time_request"]),
                            ("beacon_or_sign_state", case["beacon_or_sign_request"])):
        if context.get(field) != expected:
            raise ValueError("diagnostic school intervention differs: " + field)
    return {"diagnostic_frame_count": len(rows),
            "diagnostic_median_heavy_speed_mph": statistics.median(speeds),
            "target_speed_mph": case["speed_target_mph"],
            "physical_acceptance": "unverified",
            "legal_speed_rule_judgment": "unresolved"}


def analyze(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text())
    construction = json.loads(required(root, "construction.json").read_text())
    case_id = config["selected_case_id"]
    case = load_case(case_id)
    if (config.get("assignment_id") != ASSIGNMENT or
            construction.get("case_id") != case_id or
            case_id not in config.get("supported_case_ids", [])):
        raise ValueError("selected heavy-vehicle construction differs")
    paths = {name: required(root, name) for name in SOURCE_NAMES}
    hashes = {name: sha(path) for name, path in paths.items()}
    plan = json.loads(required(root, "case-plan.json").read_text())
    context = json.loads(paths["context.json"].read_text())
    rows = read_jsonl(paths["original-trace.jsonl"])
    receipt = json.loads(paths["receipt.json"].read_text())
    fixture = (root / "fixture-provenance.json").is_file()
    if fixture:
        provenance = json.loads(required(root, "fixture-provenance.json").read_text())
        if provenance.get("diagnostic_fixture") is not True:
            raise ValueError("diagnostic fixture provenance missing")
        measurements = diagnostic_measure(case, context, rows, receipt, paths)
    else:
        if receipt.get("camera_manifest_sha256") != hashes["cameras.json"]:
            raise ValueError("original camera source changed")
        measurements = finalize(case_id, paths["context.json"],
                                paths["original-trace.jsonl"], paths["receipt.json"])
    trace = read_jsonl(required(root, "trace.jsonl"))
    mapping = read_jsonl(required(root, "video_frames.jsonl"))
    if (len(trace) != len(rows) or len(mapping) != len(rows) or
            any(item.get("frame") != frame.get("carla_frame") or
                item.get("time_s") != frame.get("time_s")
                for item, frame in zip(trace, mapping))):
        raise ValueError("Core trace and original heavy-vehicle frame join differs")
    selected = {f"school_heavy_requirement_{index}": {
        "method": "analyze", "value": dict(measurements, requirement=entry["requirement"]),
        "sources": hashes}
        for index, entry in enumerate(plan["requirement_dispositions"])
        if entry["status"] == "selected_required" and case_id in entry["case_ids"]}
    if not selected:
        raise ValueError("selected heavy-vehicle requirement missing")
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": selected,
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["School session, timing, device and zone legal application need original review.",
                              "Diagnostic fixtures establish software behavior only."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        target = channels / (name + ".jsonl")
        source_hash = (hashes["cameras.json"] if name == "original_four_camera_pixels"
                       else hashes["original-trace.jsonl"])
        with target.open("x") as stream:
            for frame in trace:
                stream.write(json.dumps({"time_s": frame["time_s"],
                                         "value": {"source_sha256": source_hash,
                                                   "case_id": case_id,
                                                   "measurement": measurements}},
                                        sort_keys=True, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    source_target = channels / "reviewed_original_school_sources.json"
    source_target.write_text(json.dumps({"reviewed_original_school_sources": {
        "source_sha256": hashes["context.json"],
        "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_original_school_sources", "unit": "source",
                     "reference": str(source_target.relative_to(root))})
    target = case["speed_target_mph"]
    median = (measurements["diagnostic_median_heavy_speed_mph"] if fixture else
              measurements["steady_state_heavy_speed_mph_median"])
    result = {"case_id": case_id, "measured_values": measurements,
              "target_checks": [{"target": "school heavy vehicle speed engineering target",
                                 "requested": target, "measured": median,
                                 "method": "original source readback median" if not fixture else
                                           "diagnostic source readback median",
                                 "tolerance": .25, "matched": abs(median - target) <= .25,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved heavy-vehicle sources assessed; legal and physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "legal_judgment": None, "physical_acceptance_claimed": False}
    (root / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)["case_id"])


if __name__ == "__main__":
    main()
