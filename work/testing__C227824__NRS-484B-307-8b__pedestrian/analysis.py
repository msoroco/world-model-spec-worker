"""Saved-only C227824 Native result finalization.

Runs after an exited source-bound attempt is copied into a versioned analysis
workspace. It never changes original packets or asserts a legal verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from saved_entry import CAMERAS, build_report
from physical_entry import assess as assess_entry
from entry_measurement import measure_walking_speed


def _pipeline_output_root():
    source = Path(__file__).resolve()
    private = next((p for p in source.parents if p.name == ".runtime-work"), None)
    workspace = private.parent if private else source.parents[2]
    output = workspace / ".runtime-work" / "c227824-analysis-runtime"
    output.mkdir(parents=True, exist_ok=True)
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(output.resolve())
    sys.dont_write_bytecode = True
    runtime = str(workspace / "runtime" / "scenario_pipeline")
    if runtime not in sys.path:
        sys.path.insert(0, runtime)


def _jsonl(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not rows:
        raise ValueError("Missing required source: " + path.name)
    return rows


def _evidence(root, description, report):
    sources = {
        "walker_body_history": "walker-body-history.jsonl",
        "facing_signal_history": "signal-history.jsonl",
        "other_device_history": "device-history.jsonl",
        "camera_frame_map": "video_frames.jsonl",
    }
    channels = description.get("channels")
    contexts = description.get("context_inputs")
    if not isinstance(channels, list) or not isinstance(contexts, list):
        raise ValueError("declared recording channels/context missing")
    (root / "channels").mkdir(exist_ok=True)
    evidence = []
    for channel in channels:
        name = channel.get("name")
        if name not in sources or not isinstance(channel.get("unit"), str):
            raise ValueError("unsupported declared channel: " + str(name))
        rows = _jsonl(root / sources[name])
        target = root / "channels" / (name + ".jsonl")
        with target.open("x") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"], "value": row},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context = root / "channels" / "context.json"
    with context.open("x") as stream:
        stream.write(json.dumps({"highway_boundary": json.loads(
            (root / "scene.json").read_text())["highway_polygon_xy_m"],
            "source_sha256": report["source_sha256"]["scene.json"]},
            allow_nan=False) + "\n")
    for item in contexts:
        if item.get("name") != "highway_boundary" or not isinstance(item.get("unit"), str):
            raise ValueError("unsupported declared context: " + str(item.get("name")))
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(root))})
    return evidence


def finalize(attempt):
    root = Path(attempt).resolve()
    report = build_report(root)
    config = json.loads((root / "config.json").read_text())
    construction = json.loads((root / "construction.json").read_text())
    scene = json.loads((root / "scene.json").read_text())
    case_id = report["case_id"]
    if config.get("selected_case_id") != case_id or construction.get("case_id") != case_id:
        raise ValueError("saved result case differs from original construction")
    if config.get("law_id") != "NRS-484B-307-8b" or config.get("cell_id") != "C227824" or config.get("actor") != "pedestrian":
        raise ValueError("saved result exact law/cell/actor differs")
    requested = scene.get("entry_request")
    if requested not in ("entry", "wait"):
        raise ValueError("original scene lacks exact entry request")
    description = construction.get("recording_description")
    if not isinstance(description, dict):
        raise ValueError("original recording description missing")
    evidence = _evidence(root, description, report)
    observed = report["measurement"]["entry_observed"]
    target = requested == "entry"
    result = {
        "case_id": case_id,
        "measured_values": report["measurement"],
        "target_checks": [{"target": "original full-body highway entry",
                           "requested": target, "measured": observed,
                           "method": "source-joined full-body polygon/highway overlap",
                           "tolerance": 0, "matched": observed == target,
                           "physical_cause_confirmed": False,
                           "cause_evidence": report["source_sha256"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved source assessment pending physical review",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": evidence, "realized_observables": {},
    }
    _pipeline_output_root()
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(root, result)
    if scene.get("speed_mps") in (0.8, 1.2, 1.6) and "other_device_permission-" in case_id:
        original_rows = _jsonl(root / "walker-body-history.jsonl")
        observed_speed = measure_walking_speed(original_rows)
        if observed_speed is not None:
            observed_speed["reference"] = "walker-body-history.jsonl"
            result["realized_observables"]["original_pedestrian_speed_mps"] = observed_speed
    entry_check = assess_entry(report, scene, _jsonl(root / "walker-body-history.jsonl"))
    result["physical_checks"]["maneuver"] = entry_check
    result["maneuver_completed"] = entry_check["status"] == "met"
    result["behavior_attempted"] = result["physical_checks"]["target"]["status"] == "met"
    result["termination_reason"] = (
        "Saved entry or waiting source pattern assessed; legal judgment remains separate")
    validate_result(result)
    report.update({"format": "worker-analysis-report",
                   "measurements": {"pedestrian_highway_entry": {
                       "value": report["measurement"], "method": "finalize",
                       "sources": report["source_sha256"]}},
                   "physical_checks": result["physical_checks"],
                   "realized_observables": result["realized_observables"],
                   "limitations": ["Actual pixel visibility and legal permission remain unverified."],
                   "analysis_complete": True})
    return report, result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    root = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    if output != root / "analysis-report.json":
        raise ValueError("analysis report must be in the versioned analysis workspace")
    report, result = finalize(root)
    with (root / "result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
