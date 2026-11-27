"""Saved-only emergency-unit lane measurement from complete original frame joins."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from emergency_construction import CASES
from lane_probe import measure
from native_packet import AID, VIEWS

HISTORY = "original-emergency-history.jsonl"
SITE = "emergency-site.json"


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
            raise ValueError("sealed original Native emergency lane capture required")
        files = seal.get("sources")
        mandatory = {HISTORY, SITE, "camera-frame-map.jsonl", "video_frames.jsonl",
                     *[view + ".mkv" for view in VIEWS]}
        if not isinstance(files, dict) or not mandatory <= set(files):
            raise ValueError("sealed original lane source inventory incomplete")
        for name, digest in files.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or sha(required(root, name)) != digest:
                raise ValueError("sealed original lane source changed: " + name)
        revision = seal.get("native_revision", {})
        if (revision.get("construction_sha256") != sha(required(root, "construction.json"))
                or revision.get("runner_sha256") != sha(required(root, "runner.py"))):
            raise ValueError("sealed Native lane implementation changed")
        return False, {HISTORY: sha(required(root, HISTORY)), SITE: sha(required(root, SITE))}
    note = json.loads(required(root, "diagnostic-source-note.json").read_text(encoding="utf-8"))
    if (note.get("source_kind") != "synthetic_diagnostic_fixture" or
            note.get("accepted_original_source") is not False or
            note.get("case_id") != case_id):
        raise ValueError("explicit synthetic emergency lane diagnostic provenance required")
    return True, {HISTORY: sha(required(root, HISTORY)), SITE: sha(required(root, SITE))}


def check_joins(root, history):
    cameras = rows(required(root, "camera-frame-map.jsonl"))
    videos = rows(required(root, "video_frames.jsonl"))
    if len(history) != 900 or len(cameras) != 900 or len(videos) != 900:
        raise ValueError("full original emergency lane and camera history required")
    for index, (row, camera, video) in enumerate(zip(history, cameras, videos)):
        native = row["native_frame"]
        if (row["frame"] != index or camera.get("frame_index") != index
                or camera.get("native_frame") != native
                or camera.get("camera_frames") != {view: native for view in VIEWS}
                or video.get("video_frame") != index or video.get("carla_frame") != native
                or abs(camera.get("time_s", -100) - row["time_s"]) > 1e-5
                or abs(video.get("time_s", -100) - row["time_s"]) > 1e-5):
            raise ValueError("emergency lane/camera/native frame join changed")


def measure_case(case, site, history):
    return measure(case, site, history)


def analyze(root):
    root = Path(root)
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    matches = [case for case in CASES if case_id == AID + "__" + case.suffix]
    if config.get("assignment_id") != AID or len(matches) != 1:
        raise ValueError("saved exact emergency lane assignment differs")
    diagnostic, source = check_source(root, case_id)
    history = rows(required(root, HISTORY))
    check_joins(root, history)
    site = json.loads(required(root, SITE).read_text(encoding="utf-8"))
    measured = measure_case(matches[0], site, history)
    measured["original_source_sha256"] = source[HISTORY]
    channels = {
        "sealed_native_original_frames": lambda row: row["frame"],
        "unit_motion": lambda row: {"xy": row["emergency_xy"], "speed_mps": row["unit_speed_mps"]},
        "qualifying_flashing_lights": lambda row: row["flashing_light_on"],
        "visible_preparation_cue": lambda row: {"movement": row["movement_visible"], "hand_signal": row["driver_hand_signal_visible"]},
        "ego_approach": lambda row: {"xy": row["ego_xy"], "speed_mps": row["ego_speed_mps"], "approaching": row["approaching_unit"]},
        "lane_adjacency": lambda row: {"ego_lane_id": row["ego_lane_id"], "unit_lane_id": row["unit_lane_id"]},
        "nonadjacent_lane_access": lambda row: site.get("nonadjacent_route_connected"),
        "ego_lane_trajectory": lambda row: row["ego_lane_id"],
        "traffic_path_occupation": lambda row: row["traffic_path_occupied"],
        "roadway_condition": lambda row: {"nonadjacent_route_connected": site.get("nonadjacent_route_connected"),
                                               "other_hazard_path_occupied": row["other_hazard_path_occupied"]},
        "weather_condition": lambda row: {"adverse": row["weather_adverse"], "surface": row["road_surface_state"]},
        "officer_direction": lambda row: row["officer_direction"] or "none",
        "video_four_views": lambda row: row["frame"],
    }
    evidence = []
    description = config["case"]["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in channels:
            raise ValueError("unknown emergency lane recording channel: " + name)
        path = root / ("channel-" + name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"], "value": channels[name](row)}) + "\n"
                                for row in history), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": path.name})
    from worker_exchange.native_output import physical_result, write_result
    movement_m = measured["unit_displacement_m"]
    result = {"case_id": case_id, "measured_values": {"unit_displacement_m": movement_m},
        "target_checks": [{"target": "observed emergency unit displacement",
            "requested": 2.0, "measured": movement_m,
            "method": "900 sealed original Native frames" if not diagnostic else "900 synthetic diagnostic frames",
            "tolerance": 0.5, "matched": abs(movement_m - 2.0) <= 0.5,
            "physical_cause_confirmed": False, "cause_evidence": source}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "saved lane measurement pending independent physical review",
        "physical_failure_flags": [] if not diagnostic else ["original_emergency_lane_source_absent"],
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
        "measurements": {"emergency_lane_choice_and_context": {
            "method": "measure_case", "value": measured, "sources": source}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Original physical lane trajectory, target motion, pixels, and statutory possibility/safety require independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior emergency lane analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n", encoding="utf-8")
