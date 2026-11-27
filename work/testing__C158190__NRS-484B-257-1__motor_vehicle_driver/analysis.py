"""Selected saved-only nearest-view yield measurement, with explicit diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_finalizer import finalize
from yield_view_measurement import ASSIGNMENT
from yield_scene_construction import VARIANTS

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")


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
    if config.get("selected_case_id", "").endswith(("__stop_nearest_view_response", "__stop_nearest_view_uninterrupted")):
        from stop_analysis import measure as measure_stop
        return measure_stop(attempt)
    construction = json.loads(required(root, "construction.json").read_text())
    case_id = config["selected_case_id"]
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if (config.get("assignment_id") != ASSIGNMENT or suffix not in VARIANTS or
            construction.get("case_id") != case_id or
            case_id not in config.get("supported_case_ids", [])):
        raise ValueError("selected yield construction differs")
    paths = {name: required(root, name) for name in SOURCES}
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
            raise ValueError("synthetic yield fixture source seal mismatch")
        rows = [json.loads(line) for line in paths["original-trace.jsonl"].read_text().splitlines()]
        if (len(rows) != 9 or context.get("case_id") != case_id or
                context.get("control") != "yield_sign" or
                context.get("stop_line_present") is not False or
                context.get("near_crosswalk_present") is not False or
                context.get("sidewalk_derived_crosswalk_present") is not False or
                [context.get("planned_ego_response"), context.get("planned_through_traffic_phase")] !=
                list(VARIANTS[suffix])):
            raise ValueError("bounded diagnostic yield context differs")
        for i, row in enumerate(rows):
            if row.get("frame") != i or abs(row.get("time_s", -100) - i / 20) > .002:
                raise ValueError("bounded diagnostic yield cadence differs")
        value = {"diagnostic_frames": 9, "source_kind": "synthetic_fixture",
                 "legal_hazard_judgment": None, "physical_completion": "unverified"}
    else:
        value = finalize(case_id, root)
    return case_id, value, {name: sha(path) for name, path in paths.items()}, fixture, construction


def analyze(attempt, output):
    config = json.loads(required(Path(attempt), "config.json").read_text())
    if config.get("selected_case_id", "").endswith(("__stop_nearest_view_response", "__stop_nearest_view_uninterrupted")):
        from stop_analysis import analyze as analyze_stop
        return analyze_stop(attempt, output)
    root = Path(attempt)
    case_id, value, hashes, fixture, construction = measure(root)
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    expected = 9 if fixture else 900
    if len(trace) != expected:
        raise ValueError("Core trace and selected yield history count differ")
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"nearest_view_yield_event": {
                  "method": "measure", "value": value, "sources": hashes}},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["Immediate hazard and right of way require original review.",
                              "Diagnostic frames do not establish physical yield behavior."]}
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
                                                   "case_id": case_id, "measurement": value}},
                                        sort_keys=True) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context_target = channels / "reviewed_yield_site_source.json"
    context_target.write_text(json.dumps({"reviewed_yield_site_source": {
        "source_sha256": hashes["context.json"], "legal_judgment": None}}) + "\n")
    evidence.append({"name": "reviewed_yield_site_source", "unit": "source",
                     "reference": str(context_target.relative_to(root))})
    result = {"case_id": case_id, "measured_values": value,
              "target_checks": [{"target": "source-bound no-line nearest-view yield context",
                                 "requested": case_id, "measured": value,
                                 "method": "through_motion_measurement.inspect_original",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": value.get("physical_completion_probe", {}).get("status") == "met",
              "termination_reason": "Original yield-site and physical review pending",
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
