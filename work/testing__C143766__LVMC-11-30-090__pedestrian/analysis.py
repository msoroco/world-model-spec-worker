"""Saved-only finalizer for the exact pedestrian corridor cases.

The engineering band measurement is independent of legal sidewalk purpose.
Synthetic fixture provenance remains explicit in every derived report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from corridor_construction import measure_original, validate_scene
from corridor_map import verify_candidate_map

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("scene.json", "candidate-corridor.xodr", "trace.jsonl",
           "video_frames.jsonl", "walker-body-history.jsonl",
           "camera-frame-joins.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def required(root, name):
    path = root/name
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Missing required source: "+name)
    return path


def measure_original_corridor(scene, bodies):
    """Expose the executed, case-specific measurement contract method."""
    return measure_original(scene, bodies)


def build_report(attempt):
    root = Path(attempt).resolve()
    marker = json.loads(required(root, "acquisition-provenance.json").read_text())
    kind = marker.get("provenance_kind")
    fixture = marker.get("diagnostic_fixture")
    if (kind, fixture) not in (("native", False), ("synthetic_fixture", True)):
        raise ValueError("contradictory acquisition provenance")
    paths = {name: required(root, name) for name in SOURCES}
    for name in CAMERAS:
        paths[name+".mkv"] = required(root, name+".mkv")
    scene = json.loads(paths["scene.json"].read_text())
    validate_scene(scene)
    if verify_candidate_map(paths["candidate-corridor.xodr"])["map_sha256"] != scene["map_source_sha256"]:
        raise ValueError("exact corridor map source differs")
    config = json.loads(required(root, "config.json").read_text())
    if config["selected_case_id"] != scene["case_id"]:
        raise ValueError("exact case differs from source scene")
    if kind == "native":
        seal = json.loads(required(root, "capture-seal.json").read_text())
        if seal.get("provenance_kind") != "native" or seal.get("diagnostic_fixture") is not False:
            raise ValueError("Native capture seal provenance differs")
        for name, digest in seal.get("sources", {}).items():
            if sha(required(root, name)) != digest:
                raise ValueError("sealed original source changed: "+name)
    mapping = rows(paths["video_frames.jsonl"])
    trace = rows(paths["trace.jsonl"])
    bodies = rows(paths["walker-body-history.jsonl"])
    joins = rows(paths["camera-frame-joins.jsonl"])
    count = len(mapping)
    if count < 5 or (kind == "native" and count != 435) or any(
            len(group) != count for group in (trace, bodies, joins)):
        raise ValueError("incomplete original frame groups")
    for index, group in enumerate(zip(mapping, trace, bodies, joins)):
        frame_map, telemetry, body, join = group
        frame = frame_map.get("carla_frame")
        time_s = frame_map.get("time_s")
        if frame_map.get("video_frame") != index or any(
            item.get("frame") != frame or abs(item.get("time_s", -1)-time_s) > 1e-6
            for item in (telemetry, body, join)):
            raise ValueError("original body, trace, video and camera frame join failed")
        if body.get("case_id") != scene["case_id"] or join.get("case_id") != scene["case_id"]:
            raise ValueError("original frame case identity differs")
        if set(join.get("cameras", {})) != set(CAMERAS) or any(
            join["cameras"][name].get("frame") != frame for name in CAMERAS):
            raise ValueError("four original camera frame joins missing")
    measured = measure_original_corridor(scene, bodies)
    measurement_sources = ("walker-body-history.jsonl", "trace.jsonl",
                           "video_frames.jsonl", "camera-frame-joins.jsonl")
    report = {"format": "worker-analysis-report", "analysis_complete": True,
              "case_id": scene["case_id"], "provenance_kind": kind,
              "diagnostic_fixture": fixture,
              "measurements": {"pedestrian_full_body_band_occupancy": {
                  "method": "measure_original_corridor", "value": measured,
                  "sources": {name: sha(paths[name]) for name in measurement_sources}}},
              "legal_verdict_claimed": False,
              "limitations": ["Authored lane geometry does not establish municipal sidewalk purpose or trail access.",
                              "A diagnostic fixture proves software joins only, not realized Native walking or pixels."]}
    return report, config, scene, bodies, trace


def saved_result(attempt, report, config, scene, bodies, trace):
    root = Path(attempt).resolve()
    safe = next((parent for parent in root.parents if parent.name == ".runtime-work"), None)
    if safe is None:
        raise ValueError("analysis attempt must be under .runtime-work")
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(safe.resolve())
    from worker_exchange.native_output import physical_result, validate_result

    description = config["case"]["recording_description"]
    construction = json.loads(required(root, "construction.json").read_text())
    if description != construction["recording_description"]:
        raise ValueError("recording description differs from exact construction")
    values = {
        "walker_body_xy_m": [(r["time_s"], r["body_xy_m"]) for r in bodies],
        "walker_route_progress": [(r["time_s"], r["position_m"]) for r in trace],
    }
    folder = root/"channels"
    folder.mkdir(exist_ok=True)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        if name not in values:
            raise ValueError("unsupported recorded channel: "+name)
        path = folder/(name+".jsonl")
        with path.open("x") as stream:
            for time_s, value in values[name]:
                stream.write(json.dumps({"time_s": time_s, "value": value}, allow_nan=False)+"\n")
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": str(path.relative_to(root))})
    context = {"sidewalk_roadway_shoulder_trail_context": {
        "authored_map_sha256": sha(root/"candidate-corridor.xodr"),
        "bands_xy_m": scene["bounds_xy_m"],
        "sidewalk_provided_claim": scene["sidewalk_provided_claim"],
        "trail_access_status": scene["trail_access_status"],
        "camera_sources_sha256": {name: sha(root/(name+".mkv")) for name in CAMERAS}}}
    context_path = folder/"context.json"
    context_path.write_text(json.dumps(context, allow_nan=False)+"\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(root))})
    measurement = report["measurements"]["pedestrian_full_body_band_occupancy"]
    observed = measurement["value"]["all_body_inside_route_band"]
    target = {"target": "whole walker body in authored "+scene["route_band"]+" band",
              "requested": True, "measured": observed,
              "method": "original full-body polygon against source-hashed authored band",
              "tolerance": 0, "matched": observed is True,
              "physical_cause_confirmed": False,
              "cause_evidence": measurement["sources"]}
    result = {"case_id": scene["case_id"], "measured_values": measurement["value"],
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved source review pending physical assessment",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name+".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(root, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report, config, scene, bodies, trace = build_report(args.attempt)
    result = saved_result(args.attempt, report, config, scene, bodies, trace)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    with (Path(args.attempt)/"result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+"\n")
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
