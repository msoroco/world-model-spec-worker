"""Saved-only emergency-unit measurement from complete original frame joins."""

from __future__ import annotations

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path

from emergency_construction import CASES
from emergency_motion_probe import measure
from native_packet import AID, VIEWS

HISTORY = "original-emergency-history.jsonl"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def check_source(root, case_id):
    seal_path = root / "capture-seal.json"
    if seal_path.is_file():
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        if (seal.get("format") != "worker-sealed-capture" or
                seal.get("provenance_kind") != "native" or
                seal.get("diagnostic_fixture") is not False or
                seal.get("frames") != 900 or
                seal.get("restoration", {}).get("restored") is not True):
            raise ValueError("sealed original Native emergency capture required")
        files = seal.get("sources")
        mandatory = {HISTORY, "emergency-site.json", "camera-frame-map.jsonl", "video_frames.jsonl",
                     *[view + ".mkv" for view in VIEWS]}
        if not isinstance(files, dict) or not mandatory <= set(files):
            raise ValueError("sealed original emergency source inventory incomplete")
        for name, digest in files.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or sha(required(root, name)) != digest:
                raise ValueError("sealed original emergency source changed: " + name)
        revision = seal.get("native_revision", {})
        if (revision.get("construction_sha256") != sha(required(root, "construction.json"))
                or revision.get("runner_sha256") != sha(required(root, "runner.py"))):
            raise ValueError("sealed Native implementation changed")
        return False, {HISTORY: sha(required(root, HISTORY)),
                       "emergency-site.json": sha(required(root, "emergency-site.json"))}
    note_path = required(root, "diagnostic-source-note.json")
    note = json.loads(note_path.read_text(encoding="utf-8"))
    if (note.get("source_kind") != "synthetic_diagnostic_fixture" or
            note.get("accepted_original_source") is not False or
            note.get("case_id") != case_id):
        raise ValueError("explicit synthetic emergency diagnostic provenance required")
    return True, {HISTORY: sha(required(root, HISTORY)),
                  "emergency-site.json": sha(required(root, "emergency-site.json"))}


def check_joins(root, history):
    cameras = rows(required(root, "camera-frame-map.jsonl"))
    videos = rows(required(root, "video_frames.jsonl"))
    if len(history) != 900 or len(cameras) != 900 or len(videos) != 900:
        raise ValueError("full original emergency and camera history required")
    for index, (row, camera, video) in enumerate(zip(history, cameras, videos)):
        native = row["native_frame"]
        if (row["frame"] != index or camera.get("frame_index") != index
                or camera.get("native_frame") != native
                or camera.get("camera_frames") != {view: native for view in VIEWS}
                or video.get("video_frame") != index or video.get("carla_frame") != native
                or abs(camera.get("time_s", -100) - row["time_s"]) > 1e-5
                or abs(video.get("time_s", -100) - row["time_s"]) > 1e-5):
            raise ValueError("emergency/camera/native frame join changed")


def measure_case(case, site, frames):
    if case.visible and case.cue == "movement":
        return measure(site, frames)
    if len(frames) != 900:
        raise ValueError("complete emergency motion history required")
    moving = [i for i in range(1, len(frames)) if
              hypot(frames[i]["emergency_xy"][0] - frames[i-1]["emergency_xy"][0],
                    frames[i]["emergency_xy"][1] - frames[i-1]["emergency_xy"][1]) > 0]
    if not moving:
        raise ValueError("actual emergency unit movement required")
    if case.cue == "hand_signal":
        witnessed = [f["original_frame"] for f in frames if
                     f.get("driver_hand_signal_visible") is True and f.get("hand_signal_source")]
        if not witnessed:
            raise ValueError("source-bound driver hand signal missing")
    else:
        witnessed = [f["original_frame"] for f in frames if f["movement_visible"]]
        if witnessed:
            raise ValueError("occluded movement case has visible movement")
    return {"movement_original_frames": [frames[i]["original_frame"] for i in moving],
            "visible_cue_original_frames": witnessed, "prepared_to_stop": "unresolved",
            "actual_stop_required_by_clause": False}


def analyze(root):
    root = Path(root)
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    matches = [case for case in CASES if case_id == AID + "__" + case.suffix]
    if config.get("assignment_id") != AID or len(matches) != 1:
        raise ValueError("saved exact emergency assignment differs")
    diagnostic, source = check_source(root, case_id)
    history = rows(required(root, HISTORY))
    check_joins(root, history)
    site = json.loads(required(root, "emergency-site.json").read_text(encoding="utf-8"))
    measured = measure_case(matches[0], site, history)
    measured["original_source_sha256"] = source[HISTORY]
    channels = {
        "sealed_native_original_frames": lambda row: row["frame"],
        "unit_motion": lambda row: row["emergency_xy"],
        "qualifying_flashing_lights": lambda row: row["flashing_light_on"],
        "driver_view_movement_cue": lambda row: row["movement_visible"],
        "ego_approach": lambda row: {"xy": row["ego_xy"], "speed_mps": row["ego_speed_mps"]},
        "ego_response": lambda row: {"brake": row["ego_brake"], "speed_mps": row["ego_speed_mps"]},
        "officer_direction": lambda row: row["officer_direction"] or "none",
        "video_four_views": lambda row: row["frame"],
    }
    evidence = []
    description = config["case"]["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in channels:
            raise ValueError("unknown emergency recording channel: " + name)
        path = root / ("channel-" + name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"],
                                            "value": channels[name](row)}) + "\n"
                                for row in history), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": path.name})
    from worker_exchange.native_output import physical_result, write_result
    movement_m = hypot(history[-1]["emergency_xy"][0] - history[0]["emergency_xy"][0],
                       history[-1]["emergency_xy"][1] - history[0]["emergency_xy"][1])
    result = {"case_id": case_id, "measured_values": {"unit_displacement_m": movement_m},
        "target_checks": [{"target": "observed emergency unit displacement",
            "requested": 2.0, "measured": movement_m,
            "method": "900 sealed original Native frames" if not diagnostic else "900 synthetic diagnostic frames",
            "tolerance": 0.5, "matched": abs(movement_m - 2.0) <= 0.5,
            "physical_cause_confirmed": False, "cause_evidence": source}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "saved measurement pending independent physical review",
        "physical_failure_flags": [] if not diagnostic else ["original_emergency_source_absent"],
        "trace_reference": "trace.jsonl", "video_references": [view + ".mkv" for view in VIEWS],
        "video_frame_map_reference": "video_frames.jsonl", "recording_description": description,
        "recording_evidence": evidence, "realized_observables": {},
        "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case_id,
        "analysis_complete": True, "diagnostic_fixture": diagnostic,
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
        "measurements": {"emergency_movement_and_response": {
            "method": "measure_case", "value": measured, "sources": source}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Original physical motion, pixels and preparedness judgment require independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior emergency analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n", encoding="utf-8")
