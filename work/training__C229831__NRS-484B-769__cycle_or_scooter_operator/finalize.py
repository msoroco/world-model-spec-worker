"""Saved-only exact rider-arm analysis and canonical Native result writing.

No requested pose, diagnostic fixture, or synthetic pixel is a legal finding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from audit_arm_cases import audit_case
from runner import CASES


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_signal_method(audit, case_id):
    """Return exact saved pose observations, without a legal classification."""
    return {
        "case_id": case_id,
        "requested_method": audit["requested_method"],
        "right_observed_frames_in_window": audit["right_observed_frames_in_window"],
        "left_observed_frames_in_window": audit["left_observed_frames_in_window"],
        "roadway_occupied_frames": audit["roadway_occupied_frames"],
        "right_turn_route_frames": audit["right_turn_route_frames"],
        "legal_conclusion": None,
    }


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text())
    case_id = config.get("case_id") or config.get("selected_case_id")
    if case_id not in CASES:
        raise ValueError("Exact selected rider-arm case missing")
    source_names = ("rider_arm.jsonl", "camera_frames.jsonl", "road_context.json",
                    "capture-seal.json", "trace.jsonl", "video_frames.jsonl",
                    "capture/evidence.jsonl")
    for name in source_names:
        required(root, name)
    for name in CAMERAS:
        required(root, name + ".mkv")
    diagnostic_fixture = json.loads((root / "capture-seal.json").read_text()).get(
        "diagnostic_fixture") is True
    audit = audit_case(root, case_id, diagnostic_fixture=diagnostic_fixture)
    rig = rows(root / "rider_arm.jsonl")
    cameras = rows(root / "camera_frames.jsonl")
    trace = rows(root / "trace.jsonl")
    mapping = rows(root / "video_frames.jsonl")
    events = rows(root / "capture/evidence.jsonl")
    if any(len(stream) != 600 for stream in (rig, cameras, trace, mapping, events)):
        raise ValueError("Full 600-frame original source join required")
    for index, (arm, camera, motion, frame, event) in enumerate(
            zip(rig, cameras, trace, mapping, events)):
        native_frame = arm["native_frame"]
        if (arm["frame"] != index or camera["frame"] != index or
                camera["native_frame"] != native_frame or
                motion.get("frame") != native_frame or
                frame.get("video_frame") != index or
                frame.get("native_frame") != native_frame or
                event.get("original_frame") != native_frame or
                any(frame.get("camera_native_frames", {}).get(name) != native_frame
                    for name in CAMERAS)):
            raise ValueError("Original rider, camera, trace, map and event frame join differs")
    method = measure_signal_method(audit, case_id)
    measurement_sources = ("rider_arm.jsonl", "camera_frames.jsonl", "road_context.json")
    measurement = {"method": "measure_signal_method", "value": method,
                   "sources": {name: digest(root / name) for name in measurement_sources}}
    expected = 0 if CASES[case_id] == "none" else 40
    observed = (method["right_observed_frames_in_window"] if
                CASES[case_id] == "right_horizontal" else
                method["left_observed_frames_in_window"] if
                CASES[case_id] == "left_upward" else
                max(method["right_observed_frames_in_window"],
                    method["left_observed_frames_in_window"]))
    matched = observed == expected
    description = config["recording_description"]
    channel_dir = root / "channels"
    channel_dir.mkdir(exist_ok=True)
    recording = []
    for item in description["channels"]:
        name = item["name"]
        path = channel_dir / (name.replace("/", "_").replace(".", "_") + ".jsonl")
        with path.open("x") as stream:
            for frame, arm in zip(mapping, rig):
                stream.write(json.dumps({"time_s": frame["time_s"],
                    "value": {"native_frame": arm["native_frame"],
                              "rider_actor_id": arm["rider_actor_id"],
                              "bicycle_actor_id": arm["bicycle_actor_id"],
                              "bone_world_xyz_m": arm["bone_world_xyz_m"],
                              "requested_method": arm["requested_method"]}},
                    separators=(",", ":"), allow_nan=False) + "\n")
        recording.append({"name": name, "unit": item["unit"],
                          "reference": "channels/" + path.name})
    for item in description.get("context_inputs", []):
        name = item["name"]
        path = channel_dir / (name.replace("/", "_").replace(".", "_") + ".json")
        path.write_text(json.dumps({name: json.loads((root / "road_context.json").read_text())},
                                   separators=(",", ":"), allow_nan=False) + "\n")
        recording.append({"name": name, "unit": item["unit"],
                          "reference": "channels/" + path.name})
    result = {
        "case_id": case_id, "measured_values": method,
        "target_checks": [{"target": "selected_arm_pose_frames",
            "requested": expected, "measured": observed,
            "method": "sealed original rider bones, roadway and turn route; 100-139",
            "tolerance": 0, "matched": matched,
            "physical_cause_confirmed": False,
            "cause_evidence": list(measurement_sources)}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved original source window assessed; physical review pending",
        "physical_failure_flags": ["arm_pixel_visibility_and_mount_review_pending"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": recording,
        "realized_observables": {"arm_pose_frames_in_window": {
            "value": observed, "unit": "frames", "statistic": "count",
            "method": "sealed source geometry", "time_window": "frames 100-139",
            "reference": "rider_arm.jsonl"}},
        "provenance_kind": "synthetic_fixture" if diagnostic_fixture else "native",
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False,
    }
    from worker_exchange.native_output import write_result
    write_result(root, result)
    report = {"format": "worker-c229831-saved-analysis-v1",
              "case_id": case_id,
              "measurements": {"rider_arm_method_observation": measurement},
              "independent_source_audit": audit,
              "original_native_source": not diagnostic_fixture,
              "physical_visibility_verified": False,
              "legal_conclusion": None}
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
