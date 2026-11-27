"""Saved-only original-frame protected-lane measurement and Native finalization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lane_use import CASES, measure_original, require

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_NAMES = ("protected-lane-history.jsonl", "protected-lane-scene.json",
                "trace.jsonl", "video_frames.jsonl")
NATIVE_NAMES = (*SOURCE_NAMES, "road.xodr", "carla_recorder.log",
                *[name + ".mkv" for name in CAMERAS])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    case = next((item for item in CASES if case_id.endswith("__" + item.case_id)), None)
    require(case is not None and case_id.startswith(config["assignment_id"] + "__"),
            "exact protected-lane case missing")
    original = (root / "acquisition.json").is_file()
    if original:
        acquisition = json.loads(required(root, "acquisition.json").read_text(encoding="utf-8"))
        provenance = json.loads(required(root, "acquisition-provenance.json").read_text(encoding="utf-8"))
        require(provenance.get("provenance_kind") == "native" and
                provenance.get("diagnostic_fixture") is False, "original Native provenance missing")
        for name in NATIVE_NAMES:
            require(acquisition.get(name, {}).get("kind") == "original_native" and
                    acquisition[name].get("sha256") == sha(required(root, name)),
                    "original Native source changed: " + name)
    else:
        note = json.loads(required(root, "diagnostic-source-note.json").read_text(encoding="utf-8"))
        require(note.get("source_kind") == "synthetic_diagnostic_fixture" and
                note.get("accepted_original_source") is False and note.get("case_id") == case_id,
                "case-specific diagnostic provenance missing")
    scene = json.loads(required(root, "protected-lane-scene.json").read_text(encoding="utf-8"))
    history = rows(required(root, "protected-lane-history.jsonl"))
    video = rows(required(root, "video_frames.jsonl"))
    trace = rows(required(root, "trace.jsonl"))
    require(len(history) == len(video) == len(trace) == round(config["rate_hz"] * config["duration_s"]),
            "original participant, trace and video frame count differ")
    for actor, frame, telemetry in zip(history, video, trace):
        require(actor["original_frame"] == frame["carla_frame"] == telemetry["frame"] and
                actor["time_s"] == frame["time_s"] == telemetry["time_s"],
                "original participant, trace and camera frames disagree")
    require(scene.get("protected_vehicle_class") == case.protected_kind and
            scene.get("ego_vehicle_class") == "motor_vehicle",
            "reviewed participant classification differs")
    measured = measure_original(history, scene["site"], case)
    measured["diagnostic_fixture"] = not original
    source_hashes = {name: sha(root / name) for name in SOURCE_NAMES}
    description = config["case"]["recording_description"]
    channels = {
        "occupied_lane": lambda row: {"protected_id": row["protected_id"],
                                      "lane_id": scene["site"]["lane_ids"]["protected"]},
        "body_intrusion": lambda row: {"ego_xy": row["ego_xy"],
                                      "protected_xy": row["protected_xy"]},
        "protected_motion": lambda row: row["protected_speed_mps"],
        "participant_class": lambda row: {"ego": row["ego_kind"],
                                         "protected": row["protected_kind"]},
        "four_camera_visibility": lambda row: {"original_frame": row["original_frame"],
                                                 "pixel_review_status": "pending"},
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        require(name in channels, "unimplemented observation channel: " + name)
        path = root / ("channel-" + name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"],
                                            "value": channels[name](row)}) + "\n"
                                for row in history), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": path.name})
    context = root / "channel-source-context.json"
    context.write_text(json.dumps({"source_hashes": source_hashes,
                                   "original_native": original,
                                   "independent_review_pending": True,
                                   "jurisdiction": {"source": "NRS-486-341", "review_pending": True},
                                   "site_source": source_hashes["protected-lane-scene.json"],
                                   "chapter_vehicle_classification_source":
                                   scene["site"]["motorcycle_class_source_sha256"]
                                   if case.protected_kind == "motorcycle" else
                                   scene["site"]["moped_class_source_sha256"]}) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": context.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "protected motorcycle or moped full lane use",
                                 "requested": config["case"], "measured": measured,
                                 "method": "original source-bound actor history" if original else
                                           "synthetic compatibility history",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": source_hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Original independent review pending" if original else
                                    "synthetic compatibility only",
              "physical_failure_flags": [] if original else ["original_protected_lane_and_actors_absent"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}, "diagnostic_fixture": not original,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case_id,
            "analysis_complete": True, "diagnostic_fixture": not original,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": {"protected_lane_use": {"method": "analyze", "value": measured,
                                                    "sources": source_hashes}},
            "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Original highway status, occupied lane, body proximity, motion, actual pixels and legal full-use judgment require independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n", encoding="utf-8")
