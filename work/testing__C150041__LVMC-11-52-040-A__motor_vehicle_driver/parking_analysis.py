"""Saved-only C150041 measurement report and Native-shaped result draft.

The report describes observed stationary geometry. It leaves physical completion,
pixel visibility, standing/parking purpose, Chapter exceptions and law unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from parking_finalizer import finalize
from parking_pose import request
from parking_scene import ASSIGNMENT


VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
SOURCES = ("reviewed-context.json", "parking-history.jsonl", "video_frames.jsonl",
           "camera-frame-map.jsonl", "trace.jsonl", *VIDEOS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure_original(root, suffix, history_sha256):
    """Finalize original saved body and activity history against its source packet."""
    return finalize(root / "reviewed-context.json", root, suffix,
                    root / "parking-history.jsonl", history_sha256)


def _joined(root):
    history, mapping, camera, trace = [rows(root / name) for name in
        ("parking-history.jsonl", "video_frames.jsonl", "camera-frame-map.jsonl", "trace.jsonl")]
    if not len(history) == len(mapping) == len(camera) == len(trace) or len(history) < 3:
        raise ValueError("original saved frame stream lengths differ")
    previous = (-1, -math.inf)
    for index, group in enumerate(zip(history, mapping, camera, trace)):
        frame, time_s = group[0].get("frame"), group[0].get("time_s")
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not math.isfinite(time_s) or frame <= previous[0] or time_s <= previous[1]):
            raise ValueError("original saved frame identities invalid")
        if (group[1].get("carla_frame") != frame or group[1].get("video_frame") != index or
                group[2].get("frame") != frame or group[3].get("frame") != frame or
                any(abs(item.get("time_s", math.inf) - time_s) > 1e-4 for item in group)):
            raise ValueError("original saved frame/time join failed")
        if group[2].get("camera_names") != [v[:-4] for v in VIDEOS]:
            raise ValueError("original saved four-camera join differs")
        previous = (frame, time_s)
    return history, mapping, camera, trace


def analyze(attempt):
    root = Path(attempt).resolve()
    for name in SOURCES:
        if not (root / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((root / "config.json").read_text())
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-52-040-A", "C150041", "motor_vehicle_driver"):
        raise ValueError("saved analysis assignment identity differs")
    case_id = config.get("selected_case_id", "")
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("saved analysis exact case differs")
    suffix = case_id[len(ASSIGNMENT) + 2:]
    requested = request(suffix)
    if config.get("rate_hz") != 20 or [c.get("name") for c in config.get("cameras", [])] != [v[:-4] for v in VIDEOS]:
        raise ValueError("saved analysis capture contract differs")
    history, mapping, camera, trace = _joined(root)
    digest = sha(root / "parking-history.jsonl")
    measured = measure_original(root, suffix, digest)
    if measured["case_id"] != case_id or len(measured["observations"]) != len(history):
        raise ValueError("saved original history case or frame count differs")
    source_hashes = {}
    for name in SOURCES:
        path = root / name
        if not path.is_file():
            raise ValueError("missing original saved source: " + name)
        source_hashes[name] = sha(path)
    report = {"format": "worker-analysis-report", "analysis_complete": True,
              "case_id": case_id,
              "measurements": {"parking_orientation_heading_measurement": {
                  "value": measured, "method": "measure_original",
                  "sources": {name: source_hashes[name] for name in
                              ("reviewed-context.json", "parking-history.jsonl",
                               "video_frames.jsonl", "camera-frame-map.jsonl", "trace.jsonl")}}},
              "provenance_kind": "unverified_saved_source",
              "limitations": ["Native motion and actual pixels remain unverified.",
                              "Standing/parking purpose and Chapter exceptions require source review.",
                              "Engineering orientation differences are not legal thresholds."],
              "legal_verdict_claimed": False}
    final = measured["observations"][-1]
    orientation = requested[1]
    heading = requested[2]
    checks = [
        {"target": "stationary interval", "requested": True,
         "measured": bool(measured["stationary_intervals"]),
         "method": "original body/speed/control history", "tolerance": 0,
         "matched": bool(measured["stationary_intervals"]),
         "physical_cause_confirmed": False, "cause_evidence": source_hashes},
        {"target": "requested orientation", "requested": orientation,
         "measured": final["parallel_deviation_deg"],
         "method": "original full body versus reviewed roadway edge",
         "tolerance": "engineering 3 degrees for parallel; 10 degrees minimum contrast for angled",
         "matched": final["parallel_deviation_deg"] <= 3 if orientation == "parallel" else final["parallel_deviation_deg"] >= 10,
         "physical_cause_confirmed": False, "cause_evidence": source_hashes},
        {"target": "requested heading", "requested": heading,
         "measured": final["lawful_heading_deviation_deg"],
         "method": "original forward axis versus reviewed lawful direction",
         "tolerance": "engineering 3 degrees at lawful/reverse target",
         "matched": final["lawful_heading_deviation_deg"] <= 3 if heading == "lawful" else final["lawful_heading_deviation_deg"] >= 177,
         "physical_cause_confirmed": False, "cause_evidence": source_hashes},
    ]
    description = config["case"]["recording_description"]
    channel_values = {
        "body_vertices_xy_m": [row["body_vertices_xy_m"] for row in history],
        "vehicle_forward_xy": [row["vehicle_forward_xy"] for row in history],
        "speed_m_s": [row["speed_m_s"] for row in history],
        "control": [row["control"] for row in history],
        "camera_frame_map": camera,
    }
    channel_dir = root / "channels"
    channel_dir.mkdir(exist_ok=True)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        if name not in channel_values:
            raise ValueError("unsupported parking channel: " + name)
        path = channel_dir / (name + ".jsonl")
        with path.open("x") as stream:
            for row, value in zip(history, channel_values[name]):
                stream.write(json.dumps({"time_s": row["time_s"], "value": value},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": path.relative_to(root).as_posix()})
    context_path = channel_dir / "context.json"
    packet_context = json.loads((root / "reviewed-context.json").read_text())["context"]
    context_path.write_text(json.dumps({"source_sha256": source_hashes,
                                        "roadway_edge_and_polygon": {
                                            "edge_xy_m": packet_context["road_edge_xy_m"],
                                            "polygon_xy_m": packet_context["roadway_polygon_xy_m"]},
                                        "lawful_one_way_direction": packet_context["lawful_travel_xy"],
                                        "activity_and_chapter_exception_review": {
                                            "activity": packet_context["activity"],
                                            "responsible_person_role": packet_context["responsible_person_role"],
                                            "chapter_exception_review": packet_context["chapter_exception_review"]}},
                                       allow_nan=False) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": context_path.relative_to(root).as_posix()})
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": checks, "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved source measurement only; physical completion unverified",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": list(VIDEOS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {},
              "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
    return report, result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report, result = analyze(args.attempt)
    root = Path(args.attempt)
    with (root / "result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    output = Path(args.output)
    if output.exists():
        raise ValueError("saved analysis output already exists")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": result["case_id"], "analysis_complete": True,
                      "physical_acceptance_claimed": False}))
