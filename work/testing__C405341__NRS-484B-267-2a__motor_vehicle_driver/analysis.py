"""Saved-only emergency-unit measurement from complete original frame joins."""

from __future__ import annotations

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path

from emergency_construction import CASES
from native_packet import AID, VIEWS

HISTORY = "original-emergency-movement-history.jsonl"


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
        physical_site = json.loads(required(root, "emergency-site.json").read_text(encoding="utf-8"))
        if physical_site.get("speed_context", {}).get("source_kind") != "reviewed_native_conditions":
            raise ValueError("reviewed original NRS 484B.600(1) conditions required")
        return False, {HISTORY: sha(required(root, HISTORY)),
                       "emergency-site.json": sha(required(root, "emergency-site.json")),
                       "camera-frame-map.jsonl": sha(required(root, "camera-frame-map.jsonl"))}
    note_path = required(root, "diagnostic-source-note.json")
    note = json.loads(note_path.read_text(encoding="utf-8"))
    if (note.get("source_kind") != "synthetic_diagnostic_fixture" or
            note.get("accepted_original_source") is not False or
            note.get("case_id") != case_id):
        raise ValueError("explicit synthetic emergency diagnostic provenance required")
    return True, {HISTORY: sha(required(root, HISTORY)),
                  "emergency-site.json": sha(required(root, "emergency-site.json")),
                  "camera-frame-map.jsonl": sha(required(root, "camera-frame-map.jsonl"))}


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
    """Observe cues without turning motion or response into a legal cutoff."""
    if len(frames) != 900:
        raise ValueError("complete emergency motion history required")
    if site.get("target_vehicle_class") != case.unit_class:
        raise ValueError("target vehicle source differs from exact case")
    if site.get("light_request") != case.light_request:
        raise ValueError("flashing equipment/use source differs from exact case")
    context = site.get("speed_context")
    if not isinstance(context, dict):
        raise ValueError("original NRS 484B.600(1) speed context required")
    for condition in ("traffic", "surface", "highway_width", "weather", "other_highway_conditions"):
        item = context.get(condition)
        if not isinstance(item, dict) or not item.get("source_ref") or item.get("observed_value") is None:
            raise ValueError("original reasonable-speed condition missing: " + condition)
    moving = [i for i in range(1, len(frames)) if
              hypot(frames[i]["emergency_xy"][0] - frames[i-1]["emergency_xy"][0],
                    frames[i]["emergency_xy"][1] - frames[i-1]["emergency_xy"][1]) > 0]
    visible_movement = [f["original_frame"] for f in frames if f["movement_visible"]]
    visible_hand = [f["original_frame"] for f in frames if
                    f["driver_hand_signal_visible"] and f["hand_signal_source"]]
    if case.cue == "none" and moving:
        raise ValueError("no-movement comparison has actual target motion")
    if case.cue == "visible_hand_signal" and not visible_hand:
        raise ValueError("source-bound driver hand signal missing")
    if case.cue == "occluded_movement" and visible_movement:
        raise ValueError("occluded movement case has visible movement")
    if case.cue in {"visible_movement", "already_moving"} and not visible_movement:
        raise ValueError("visible movement source missing")
    if case.cue in {"visible_movement", "occluded_movement", "already_moving"} and not moving:
        raise ValueError("movement comparison has no actual target motion")
    if case.light_request == "qualified_inactive" and any(f["flashing_light_on"] for f in frames):
        raise ValueError("inactive flashing-light comparison has active lights")
    if case.light_request != "qualified_inactive" and not any(f["flashing_light_on"] for f in frames):
        raise ValueError("active flashing-light comparison has no active lights")
    if case.officer_direction and not any(f["officer_direction"] for f in frames):
        raise ValueError("officer-direction comparison lacks original direction")
    speeds = [f["ego_speed_mps"] for f in frames]
    if any(type(speed) not in (int, float) or speed < 0 for speed in speeds):
        raise ValueError("original nonnegative ego speed history required")
    for previous, current in zip(frames, frames[1:]):
        elapsed = current["time_s"] - previous["time_s"]
        if elapsed <= 0:
            raise ValueError("nonmonotone original ego speed history")
        traveled = hypot(current["ego_xy"][0] - previous["ego_xy"][0],
                         current["ego_xy"][1] - previous["ego_xy"][1]) / elapsed
        lower = min(previous["ego_speed_mps"], current["ego_speed_mps"])
        upper = max(previous["ego_speed_mps"], current["ego_speed_mps"])
        if traveled < lower - 1.0 or traveled > upper + 1.0:
            raise ValueError("ego speed and original pose history disagree")
    return {"movement_original_frames": [frames[i]["original_frame"] for i in moving],
            "visible_movement_original_frames": visible_movement,
            "visible_hand_original_frames": visible_hand,
            "ego_speed_initial_mps": speeds[0],
            "ego_speed_final_mps": speeds[-1],
            "ego_speed_decrease_mps": speeds[0] - speeds[-1],
            "reasonable_speed_context": context,
            "about_to_move_judgment": "unresolved",
            "reasonable_and_proper_speed_judgment": "unresolved"}


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
        "target_authorization": lambda row: site["target_vehicle_class"],
        "driver_view_movement_cue": lambda row: row["movement_visible"],
        "driver_hand_signal": lambda row: row["driver_hand_signal_visible"],
        "ego_approach": lambda row: {"xy": row["ego_xy"], "speed_mps": row["ego_speed_mps"]},
        "ego_response": lambda row: {"brake": row["ego_brake"], "speed_mps": row["ego_speed_mps"]},
        "reasonable_speed_context": lambda row: site["speed_context"],
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
    final_speed = history[-1]["ego_speed_mps"]
    requested_speed = 5.0 if matches[0].reduce_speed else 7.5
    result = {"case_id": case_id, "measured_values": {
        "unit_displacement_m": movement_m,
        "ego_speed_initial_mps": history[0]["ego_speed_mps"],
        "ego_speed_final_mps": final_speed,
        "ego_speed_decrease_mps": history[0]["ego_speed_mps"] - final_speed},
        "target_checks": [{"target": "observed emergency unit displacement",
            "requested": 0.0 if matches[0].cue in {"none", "visible_hand_signal"} else 2.0,
            "measured": movement_m,
            "method": "900 sealed original Native frames" if not diagnostic else "900 synthetic diagnostic frames",
            "tolerance": 0.5,
            "matched": abs(movement_m - (0.0 if matches[0].cue in {"none", "visible_hand_signal"} else 2.0)) <= 0.5,
            "physical_cause_confirmed": False, "cause_evidence": source},
            {"target": "authored physical ego speed response; no legal threshold",
             "requested": requested_speed, "measured": final_speed,
             "method": "900 original ego speed samples joined to the visible movement cue",
             "tolerance": 0.5, "matched": abs(final_speed - requested_speed) <= 0.5,
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
        "measurements": {"emergency_movement_and_visibility": {
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
