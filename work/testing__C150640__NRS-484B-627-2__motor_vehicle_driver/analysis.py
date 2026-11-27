"""Saved-only stop and traffic-effect finalizer; legal judgments remain open."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stop_model import ASSIGNMENT, BY_NAME, measure_original


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("stop-history.jsonl", "stop-scene.json", "video_frames.jsonl", "trace.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def verify_join(history, mapping, trace):
    if not history or len(history) != len(mapping) or len(history) != len(trace):
        raise ValueError("original participant, trace and camera counts differ")
    for participant, camera, telemetry in zip(history, mapping, trace):
        key = (participant["original_frame"], participant["time_s"])
        if key != (camera["carla_frame"], camera["time_s"]):
            raise ValueError("original stop and camera frame/time disagree")
        if key != (telemetry["frame"], telemetry["time_s"]):
            raise ValueError("original stop and trace frame/time disagree")


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    if not case_id.startswith(ASSIGNMENT + "__") or case_id.split("__")[-1] not in BY_NAME:
        raise ValueError("selected exact stop case missing")
    case = BY_NAME[case_id.split("__")[-1]]
    original = (root / "acquisition.json").is_file()
    if original:
        acquisition = json.loads(required(root, "acquisition.json").read_text(encoding="utf-8"))
        for name in (*SOURCES, "road.xodr", "carla_recorder.log",
                     *[camera + ".mkv" for camera in CAMERAS]):
            if (acquisition.get(name, {}).get("kind") != "original_native"
                    or acquisition[name].get("sha256") != sha(required(root, name))):
                raise ValueError("original Native stop source changed: " + name)
        provenance = json.loads(required(root, "acquisition-provenance.json").read_text())
        if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
            raise ValueError("original Native stop provenance missing")
    else:
        note = json.loads(required(root, "diagnostic-source-note.json").read_text())
        if note.get("source_kind") != "synthetic_diagnostic_fixture" or note.get("accepted_original_source") is not False:
            raise ValueError("synthetic stop compatibility provenance missing")
    scene = json.loads(required(root, "stop-scene.json").read_text(encoding="utf-8"))
    history = rows(required(root, "stop-history.jsonl"))
    mapping = rows(required(root, "video_frames.jsonl"))
    trace = rows(required(root, "trace.jsonl"))
    verify_join(history, mapping, trace)
    measured = measure_original(history, scene, case)
    measured["diagnostic_fixture"] = not original
    values = {
        "scene_source": lambda row: {"kind": "original_native" if original else "synthetic_diagnostic"},
        "one_way_route": lambda row: scene["one_way_route"],
        "ego_driver_and_vehicle": lambda row: {"ego_id": row["ego_id"], "driver_source": scene["sources"]["ego_driver"]["sha256"]},
        "ego_motion": lambda row: row["ego_speed_mps"],
        "roadway_footprint": lambda row: row["ego_footprint_xy"],
        "follower_motion": lambda row: {"speed_mps": row["follower_speed_mps"],
                                           "station_m": row["follower_route_station_m"],
                                           "body_gap_m": row.get("body_gap_m")},
        "passing_space": lambda row: scene["passing_space_m"],
        "stop_purpose": lambda row: {"requested": case.stop_reason,
                                      "source": scene["sources"]["stop_purpose"]["sha256"]},
        "conflict_context": lambda row: {"readback": row.get("conflict_readback"),
                                         "present": row.get("conflict_readback") is not None},
        "official_direction_context": lambda row: {"readback": row.get("official_direction_readback"),
                                                   "present": row.get("official_direction_readback") is not None},
        "camera_frame_map": lambda row: {"frame": row["original_frame"], "time_s": row["time_s"]},
    }
    recording = config["case"]["recording_description"]
    evidence = []
    for channel in recording["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unknown original stop channel: " + name)
        path = root / ("channel-" + name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"], "value": values[name](row)}) + "\n"
                                for row in history), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": path.name})
    for item in recording.get("context_inputs", []):
        context = root / ("context-" + item["name"] + ".json")
        context.write_text(json.dumps({item["name"]: {
            "source_sha256": scene["sources"][item["name"]]["sha256"],
            "review_status": "pending_local_original_review"}}) + "\n")
        evidence.append({"name": item["name"], "unit": item["unit"], "reference": context.name})
    from worker_exchange.native_output import physical_result, write_result
    hashes = {name: sha(root / name) for name in SOURCES}
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "actual stop, footprint and follower history",
                                 "requested": config["case"], "measured": measured,
                                 "method": "original source-bound Native history" if original else "synthetic compatibility history",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Original independent review pending" if original else "synthetic compatibility only",
              "physical_failure_flags": [] if original else ["original_roadway_stop_and_traffic_absent"],
              "trace_reference": "trace.jsonl",
              "video_references": [camera + ".mkv" for camera in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": recording,
              "recording_evidence": evidence,
              "realized_observables": {}, "diagnostic_fixture": not original,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    write_result(root, physical_result(root, result))
    measurements = {}
    named = ("complete_stop", "roadway_position", "traffic_effect", "safety_context", "law_direction")
    for key in named:
        measurements[key] = {"method": "analyze", "value": measured, "sources": hashes}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "analysis_complete": True, "diagnostic_fixture": not original,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements,
            "limitations": ["Physical traffic effect and both statutory exceptions require independent original review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n", encoding="utf-8")
