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
        mandatory = {HISTORY, "emergency-site.json", "config.json", "trace.jsonl",
                     "camera-frame-map.jsonl", "video_frames.jsonl",
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
    trace = rows(required(root, "trace.jsonl"))
    if len(history) != 900 or len(cameras) != 900 or len(videos) != 900 or len(trace) != 900:
        raise ValueError("full original emergency and camera history required")
    for index, (row, camera, video, motion) in enumerate(zip(history, cameras, videos, trace)):
        native = row["native_frame"]
        if (row["frame"] != index or camera.get("frame_index") != index
                or camera.get("native_frame") != native
                or camera.get("camera_frames") != {view: native for view in VIEWS}
                or video.get("video_frame") != index or video.get("carla_frame") != native
                or abs(camera.get("time_s", -100) - row["time_s"]) > 1e-5
                or abs(video.get("time_s", -100) - row["time_s"]) > 1e-5):
            raise ValueError("emergency/camera/native frame join changed")
        pose = motion.get("position_m")
        control = motion.get("control")
        if (motion.get("frame") != native or
                abs(motion.get("time_s", -100) - row["time_s"]) > 1e-5 or
                not isinstance(pose, list) or len(pose) < 2 or
                not isinstance(control, dict) or
                abs(pose[0] - row["ego_xy"][0]) > 0.05 or
                abs(pose[1] - row["ego_xy"][1]) > 0.05 or
                abs(motion.get("speed_mps", -100) - row["ego_speed_mps"]) > 0.05 or
                abs(control.get("brake", -100) - row["ego_brake"]) > 0.02):
            raise ValueError("emergency/subject trace source join changed")


def measure_case(case, site, frames):
    """Observe approach and response without imposing a legal distance cutoff."""
    if len(frames) != 900:
        raise ValueError("complete emergency motion history required")
    if site.get("target_vehicle_class") != case.unit_class:
        raise ValueError("target vehicle source differs from exact case")
    if site.get("subject_vehicle_class") != "ordinary_motor_vehicle" or not site.get("subject_driver_source"):
        raise ValueError("every-other-vehicle driver source missing")
    if site.get("light_request") != case.light_request:
        raise ValueError("flashing equipment/use source differs from exact case")
    for key in ("authorization_source", "qualifying_lights_source", "light_rule_source",
                "front_visible_red_lamp_source", "siren_equipment_source", "route_source"):
        if not site.get(key):
            raise ValueError("missing original authority or equipment source: " + key)
    if case.light_request != "unqualified_active" and site.get("front_visible_red_lamp_qualified") is not True:
        raise ValueError("qualified front-visible red lamp source missing")
    if site.get("immediate_approach_request") is not case.immediate:
        raise ValueError("immediate approach request differs from exact case")
    if site.get("yield_response_request") is not case.yielding:
        raise ValueError("yield response request differs from exact case")
    if site.get("approach_direction") != case.direction:
        raise ValueError("approach direction differs from exact case")
    if site.get("unit_state") != case.state:
        raise ValueError("moving, preparing or stopped state differs from exact case")
    if case.state == "preparing" and not site.get("visible_preparation_source"):
        raise ValueError("visible preparation source missing")
    moving = [i for i in range(1, len(frames)) if
              hypot(frames[i]["emergency_xy"][0] - frames[i-1]["emergency_xy"][0],
                    frames[i]["emergency_xy"][1] - frames[i-1]["emergency_xy"][1]) > 0]
    visible_movement = [f["original_frame"] for f in frames if f["movement_visible"]]
    hand_signals = [f["original_frame"] for f in frames if f.get("visible_hand_signal")]
    if case.state == "moving" and not moving:
        raise ValueError("emergency approach has no actual target motion")
    if case.state == "preparing" and (not moving or not hand_signals or
            moving[0] <= 400 or max(hand_signals) >= frames[moving[0]]["original_frame"]):
        raise ValueError("visible preparation must precede original target movement")
    if case.state == "stopped" and (moving or hand_signals):
        raise ValueError("stopped referral must lack movement and preparation")
    if case.light_request == "qualified_inactive" and any(f["flashing_light_on"] for f in frames):
        raise ValueError("inactive flashing-light comparison has active lights")
    if case.light_request != "qualified_inactive" and not any(f["flashing_light_on"] for f in frames):
        raise ValueError("active flashing-light comparison has no active lights")
    if case.officer_direction and not any(f["officer_direction"] for f in frames):
        raise ValueError("officer-direction comparison lacks original direction")
    early = [hypot(f["ego_xy"][0] - f["emergency_xy"][0],
                   f["ego_xy"][1] - f["emergency_xy"][1]) for f in frames[:400]]
    if case.immediate and case.state == "moving" and not min(early[1:]) < early[0]:
        raise ValueError("unit does not approach subject in original frames")
    if case.state == "preparing":
        after = [hypot(f["ego_xy"][0] - f["emergency_xy"][0],
                       f["ego_xy"][1] - f["emergency_xy"][1]) for f in frames[400:600]]
        if not min(after[1:]) < after[0]:
            raise ValueError("prepared unit does not approach subject after cue")
    brakes = [f["original_frame"] for f in frames if f["ego_brake"] > 0]
    if case.yielding and not brakes:
        raise ValueError("requested yielding has no brake response")
    if not case.yielding and brakes:
        raise ValueError("no-yield contrast has brake response")
    return {"movement_original_frames": [frames[i]["original_frame"] for i in moving],
            "visible_movement_original_frames": visible_movement,
            "visible_hand_signal_original_frames": hand_signals,
            "unit_state": case.state,
            "subsection_1_referral": case.state != "stopped" and case.immediate,
            "first_brake_original_frame": brakes[0] if brakes else None,
            "initial_center_distance_m": early[0],
            "minimum_early_center_distance_m": min(early),
            "immediate_approach_judgment": "unresolved",
            "right_of_way_yield_judgment": "unresolved"}


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
        "unit_state": lambda row: site["unit_state"],
        "subsection_1_referral": lambda row: matches[0].state != "stopped" and matches[0].immediate,
        "front_visible_red_lamp": lambda row: site["front_visible_red_lamp_source"],
        "siren_equipment": lambda row: site["siren_equipment_source"],
        "target_authorization": lambda row: site["target_vehicle_class"],
        "subject_driver": lambda row: {"class": site["subject_vehicle_class"],
                                         "driver_source": site["subject_driver_source"]},
        "driver_view_movement_cue": lambda row: row["movement_visible"],
        "relative_approach": lambda row: {"ego_xy": row["ego_xy"], "unit_xy": row["emergency_xy"]},
        "right_of_way_order": lambda row: {"ego_brake": row["ego_brake"], "ego_speed_mps": row["ego_speed_mps"]},
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
        "target_checks": [{"target": "observed emergency unit movement",
            "requested": True,
            "measured": movement_m > 0,
            "method": "900 sealed original Native frames" if not diagnostic else "900 synthetic diagnostic frames",
            "tolerance": None,
            "matched": movement_m > 0,
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
        "measurements": {"emergency_approach_and_yield_response": {
            "method": "measure_case", "value": measured, "sources": source}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Original physical approach, light pixels and right-of-way yielding require independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior emergency analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n", encoding="utf-8")
