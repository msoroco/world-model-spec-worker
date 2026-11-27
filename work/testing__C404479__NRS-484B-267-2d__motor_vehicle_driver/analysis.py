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
    """Measure original body ordering without inventing a statutory time or gap cutoff."""
    if len(frames) != 900:
        raise ValueError("complete original adjacent-lane motion history required")
    if site.get("target_vehicle_class") != case.unit_class:
        raise ValueError("target vehicle source differs from exact case")
    if site.get("subject_vehicle_class") != "ordinary_motor_vehicle" or not site.get("subject_driver_source"):
        raise ValueError("every-other-vehicle driver source missing")
    if site.get("light_request") != case.light_request:
        raise ValueError("flashing equipment/use source differs from exact case")
    if site.get("passing_maneuver_request") != case.maneuver:
        raise ValueError("passing maneuver differs from exact case")
    if site.get("immediate_approach_request") is not case.immediate:
        raise ValueError("subject approach request differs from exact case")
    if site.get("approach_direction") != "same_direction":
        raise ValueError("same-direction source missing")
    if site.get("unit_state") != case.state:
        raise ValueError("moving or visibly preparing state differs from exact case")
    for key in ("authorization_source", "qualifying_lights_source", "light_rule_source",
                "route_source", "adjacent_traversable_lanes_source", "passing_clearance_source",
                "ego_body_extent_source", "unit_body_extent_source"):
        if not site.get(key):
            raise ValueError("missing original authority, route, lane or extent source: " + key)
    if case.state == "preparing" and not site.get("visible_preparation_source"):
        raise ValueError("visible preparation source missing")
    movement = [i for i in range(1, len(frames))
                if frames[i]["emergency_xy"] != frames[i - 1]["emergency_xy"]]
    if not movement:
        raise ValueError("target unit has no original movement")
    hand = [f["original_frame"] for f in frames if f.get("visible_hand_signal")]
    if case.state == "preparing" and (not hand or min(movement) <= 400
            or max(hand) >= frames[min(movement)]["original_frame"]):
        raise ValueError("visible hand signal must precede target movement")
    if case.light_request == "qualified_inactive" and any(f["flashing_light_on"] for f in frames):
        raise ValueError("inactive light contrast has active lights")
    if case.light_request != "qualified_inactive" and not any(f["flashing_light_on"] for f in frames):
        raise ValueError("active light contrast has no flashing use")
    if case.officer_direction and not any(f["officer_direction"] for f in frames):
        raise ValueError("officer direction missing from original history")
    overlap = []
    ego_ahead = []
    unit_ahead = []
    for f in frames:
        ego = f.get("ego_body_polygon_xy")
        unit = f.get("emergency_body_polygon_xy")
        if not isinstance(ego, list) or len(ego) < 4 or not isinstance(unit, list) or len(unit) < 4:
            raise ValueError("original body-footprint polygons required")
        tangent, other_tangent = f.get("ego_route_tangent_xy"), f.get("unit_route_tangent_xy")
        if tangent != [1.0, 0.0] or other_tangent != [1.0, 0.0]:
            raise ValueError("reviewed same-direction route tangent required")
        ex = [point[0] for point in ego]
        ux = [point[0] for point in unit]
        ey = [point[1] for point in ego]
        uy = [point[1] for point in unit]
        if (min(ex) >= max(ex) or min(ux) >= max(ux)
                or min(ex) > f["ego_xy"][0] or max(ex) < f["ego_xy"][0]
                or min(ux) > f["emergency_xy"][0] or max(ux) < f["emergency_xy"][0]
                or min(ey) > f["ego_xy"][1] or max(ey) < f["ego_xy"][1]
                or min(uy) > f["emergency_xy"][1] or max(uy) < f["emergency_xy"][1]):
            raise ValueError("body polygons do not enclose original actor poses")
        if max(ey) >= min(uy):
            raise ValueError("adjacent lane body clearance failed")
        overlap.append(min(max(ex), max(ux)) - max(min(ex), min(ux)) >= 0)
        ego_ahead.append(min(ex) > max(ux))
        unit_ahead.append(min(ux) > max(ex))
    started_behind = unit_ahead[0]
    started_ahead = ego_ahead[0]
    ego_overtook = started_behind and any(overlap) and any(ego_ahead)
    unit_overtook = started_ahead and any(overlap) and any(unit_ahead)
    approach = min(abs(f["emergency_xy"][0] - f["ego_xy"][0]) for f in frames[1:400]) < abs(
        frames[0]["emergency_xy"][0] - frames[0]["ego_xy"][0])
    if case.immediate and not approach:
        raise ValueError("subject does not approach target on original frames")
    if not case.immediate and case.maneuver != "unit_overtakes" and approach:
        raise ValueError("no-approach contrast approaches target")
    if case.maneuver == "overtake" and not ego_overtook:
        raise ValueError("ego overtake lacks complete behind-to-ahead body ordering")
    if case.maneuver == "abreast" and (not any(overlap) or ego_overtook):
        raise ValueError("abreast contrast lacks body overlap or becomes overtake")
    if case.maneuver == "unit_overtakes" and not unit_overtook:
        raise ValueError("unit-overtakes contrast lacks reverse body ordering")
    if case.maneuver == "hold_behind" and (any(overlap) or ego_overtook):
        raise ValueError("hold-behind contrast becomes abreast or overtake")
    return {
        "moving_original_frames": [frames[i]["original_frame"] for i in movement],
        "visible_hand_signal_original_frames": hand,
        "first_abreast_original_frame": next((f["original_frame"] for f, yes in zip(frames, overlap) if yes), None),
        "first_ego_ahead_original_frame": next((f["original_frame"] for f, yes in zip(frames, ego_ahead) if yes), None),
        "first_unit_ahead_original_frame": next((f["original_frame"] for f, yes in zip(frames, unit_ahead) if yes), None),
        "ego_overtook": ego_overtook, "unit_overtook": unit_overtook,
        "subject_approach_observed": approach,
        "abreast_observed": any(overlap),
        "qualifying_lights_judgment": "unresolved",
        "legal_abreast_overtake_judgment": "unresolved",
    }

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
        "qualifying_flashing_lights": lambda row: {"on": row["flashing_light_on"],
            "qualification_source": site["qualifying_lights_source"],
            "rule_source": site["light_rule_source"]},
        "unit_state": lambda row: {"requested": site["unit_state"],
                                    "original_movement_visible": row["movement_visible"],
                                    "original_hand_signal_visible": bool(row.get("visible_hand_signal"))},
        "same_direction_routes": lambda row: {"ego_tangent": row["ego_route_tangent_xy"],
                                               "unit_tangent": row["unit_route_tangent_xy"],
                                               "route_source": site["route_source"]},
        "target_authorization": lambda row: {"class": site["target_vehicle_class"],
                                               "source": site["authorization_source"]},
        "subject_driver": lambda row: {"class": site["subject_vehicle_class"],
                                         "driver_source": site["subject_driver_source"]},
        "driver_view_movement_cue": lambda row: {"movement_visible": row["movement_visible"],
                                                   "hand_signal_visible": bool(row.get("visible_hand_signal"))},
        "relative_approach": lambda row: {"ego_xy": row["ego_xy"], "unit_xy": row["emergency_xy"]},
        "abreast_overtake_order": lambda row: {
            "ego_body_polygon_xy": row["ego_body_polygon_xy"],
            "unit_body_polygon_xy": row["emergency_body_polygon_xy"],
            "ego_speed_mps": row["ego_speed_mps"],
            "unit_speed_mps": row["unit_speed_mps"]},
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
    observed_maneuver = {
        "hold_behind": not measured["abreast_observed"] and not measured["ego_overtook"],
        "overtake": measured["ego_overtook"],
        "abreast": measured["abreast_observed"] and not measured["ego_overtook"],
        "unit_overtakes": measured["unit_overtook"],
    }[matches[0].maneuver]
    result = {"case_id": case_id, "measured_values": {
        "unit_displacement_m": movement_m,
        "abreast_observed": measured["abreast_observed"],
        "ego_overtook": measured["ego_overtook"],
        "unit_overtook": measured["unit_overtook"]},
        "target_checks": [{"target": "observed emergency unit movement",
            "requested": True,
            "measured": movement_m > 0,
            "method": "900 sealed original Native frames" if not diagnostic else "900 synthetic diagnostic frames",
            "tolerance": None,
            "matched": movement_m > 0,
            "physical_cause_confirmed": False, "cause_evidence": source},
            {"target": "original body-order maneuver", "requested": matches[0].maneuver,
             "measured": observed_maneuver, "method": "900 source-joined actor body polygons",
             "tolerance": None, "matched": observed_maneuver,
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
        "measurements": {"same_direction_abreast_overtake": {
            "method": "measure_case", "value": measured, "sources": source}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Original physical approach, light pixels, body extents and legal overtaking judgment require independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior emergency analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n", encoding="utf-8")
