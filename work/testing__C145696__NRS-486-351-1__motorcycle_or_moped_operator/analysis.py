"""Saved-only original-frame adjacent-lane measurements and Native finalization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lane_split import measure_original, require

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ORIGINAL_SOURCES = ("lane-split-history.jsonl", "lane-split-scene.json",
                    "trace.jsonl", "video_frames.jsonl", "road.xodr", "carla_recorder.log",
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
    case = config["case"]
    original = (root / "acquisition.json").is_file()
    source_names = (ORIGINAL_SOURCES if original else
                    ("lane-split-history.jsonl", "lane-split-scene.json",
                     "trace.jsonl", "video_frames.jsonl"))
    if original:
        acquisition = json.loads(required(root, "acquisition.json").read_text(encoding="utf-8"))
        provenance = json.loads(required(root, "acquisition-provenance.json").read_text(encoding="utf-8"))
        require(provenance.get("provenance_kind") == "native" and
                provenance.get("diagnostic_fixture") is False, "original Native provenance missing")
        for name in source_names:
            require(acquisition.get(name, {}).get("kind") == "original_native" and
                    acquisition[name].get("sha256") == sha(required(root, name)),
                    "original Native source changed: " + name)
    else:
        marker = json.loads(required(root, "diagnostic-source-note.json").read_text(encoding="utf-8"))
        require(marker.get("source_kind") == "synthetic_diagnostic_fixture" and
                marker.get("accepted_original_source") is False and
                marker.get("case_id") == case_id, "case-specific diagnostic provenance missing")
    scene = json.loads(required(root, "lane-split-scene.json").read_text(encoding="utf-8"))
    history = rows(required(root, "lane-split-history.jsonl"))
    mapping = rows(required(root, "video_frames.jsonl"))
    trace = rows(required(root, "trace.jsonl"))
    require(len(history) == len(mapping) == len(trace) == round(config["rate_hz"] * config["duration_s"]),
            "original participant, trace and video frame count differ")
    for actor, video, telemetry in zip(history, mapping, trace):
        require(actor["frame"] == video["carla_frame"] == telemetry["frame"] and
                actor["time_s"] == video["time_s"] == telemetry["time_s"],
                "original participant, trace and camera frames disagree")
    require(scene.get("operator_status") == case["operator_status"] and
            scene.get("performance_of_duty") == case["performance_of_duty"] and
            scene.get("ego_vehicle_class") == case["vehicle_class"],
            "operator duty or chapter vehicle class differs")
    expected = scene["participant_readback"]
    measured = measure_original(history, expected)
    measured["operator_status"] = scene["operator_status"]
    measured["performance_of_duty"] = scene["performance_of_duty"]
    measured["ego_vehicle_class"] = scene["ego_vehicle_class"]
    measured["classification_source_sha256"] = scene["classification_source_sha256"]
    measured["operator_identity_source_sha256"] = scene["operator_identity_source_sha256"]
    measured["police_status_source_sha256"] = scene["police_status_source_sha256"]
    measured["performance_of_duty_source_sha256"] = scene["performance_of_duty_source_sha256"]
    measured["diagnostic_fixture"] = not original
    source_hashes = {name: sha(root / name) for name in
                     ("lane-split-history.jsonl", "lane-split-scene.json", "trace.jsonl", "video_frames.jsonl")}
    channels = {
        "adjacent_lane_occupancy": lambda row: {"left_lane_id": row["actors"]["left_occupant"]["lane_id"],
                                                  "right_lane_id": row["actors"]["right_occupant"]["lane_id"]},
        "between_vehicle_passage": lambda row: {"ego": row["actors"]["ego"],
                                                  "left": row["actors"]["left_occupant"],
                                                  "right": row["actors"]["right_occupant"]},
        "vehicle_motion": lambda row: {role: body["speed_mps"] for role, body in row["actors"].items()},
        "ego_vehicle_class": lambda row: {"value": scene["ego_vehicle_class"],
                                             "source_sha256": scene["classification_source_sha256"]},
        "police_duty_exception": lambda row: {"operator_status": scene["operator_status"],
                                                "performance_of_duty": scene["performance_of_duty"],
                                                "source_sha256": scene["performance_of_duty_source_sha256"]},
        "four_camera_visibility": lambda row: {"original_frame": row["frame"],
                                                 "pixel_review_status": "pending"},
    }
    description = config["case"]["recording_description"]
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        require(name in channels, "unimplemented observation channel: " + name)
        path = root / ("channel-" + name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"], "value": channels[name](row)}) + "\n"
                                for row in history), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": path.name})
    context = root / "channel-source-context.json"
    context.write_text(json.dumps({"source_hashes": source_hashes,
                                   "original_native": original,
                                   "independent_review_pending": True,
                                   "jurisdiction": {"source": "NRS-486-351-1", "review_pending": True},
                                   "lane_geometry_source": source_hashes["lane-split-scene.json"],
                                   "operator_identity_source": scene["operator_identity_source_sha256"],
                                   "police_status_source": scene["police_status_source_sha256"],
                                   "performance_of_duty_source": scene["performance_of_duty_source_sha256"],
                                   "chapter_vehicle_classification_source": scene["classification_source_sha256"]}) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"], "reference": context.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "original adjacent-lane occupants and motorcycle/moped passage",
                                 "requested": case, "measured": measured,
                                 "method": "original source-bound participant history" if original else
                                           "synthetic compatibility history",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False, "cause_evidence": source_hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Original independent review pending" if original else
                                    "synthetic compatibility only",
              "physical_failure_flags": [] if original else ["original_lane_occupants_and_operator_absent"],
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
            "measurements": {"adjacent_lane_passage": {"method": "analyze", "value": measured,
                                                      "sources": source_hashes}},
            "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Actual lane occupancy, physical passage, video pixels, identity, duty status and legal outcome require original independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
