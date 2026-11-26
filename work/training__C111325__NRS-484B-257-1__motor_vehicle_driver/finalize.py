"""Saved-only stop/yield analysis; no replay, legal verdict or physical claim."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from measure_saved_packet import inspect
from native_capture import CAMERAS, COUNT
from worker_exchange.native_output import physical_result, write_result


def required(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing required source: " + relative)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(root, relative):
    return [json.loads(line) for line in required(root, relative).read_text().splitlines() if line.strip()]


def selected_sources(root, names):
    return {name: sha(required(root, name)) for name in names}


def measure_stop_sign(observed):
    return {"sign_kind": observed["sign_kind"],
            "rest_frames_before_reference": observed["rest_frames_before_reference"],
            "minimum_speed_before_reference_mps": observed["minimum_speed_before_reference_mps"],
            "legal_stop_duty": "unassessed"}


def measure_reference(observed):
    return {"reference_kind": observed["stopping_reference"],
            "first_reference_crossing_frame": observed["first_reference_crossing_frame"],
            "legal_reference_compliance": "unassessed"}


def measure_through_duty(observed):
    return {"intersection_entry_frame": observed["intersection_entry_frame"],
            "intersection_last_frame": observed["intersection_last_frame"],
            "entered_frames": observed["through_entered_while_crossing_frames"],
            "approaching_frames": observed["through_approaching_while_crossing_frames"],
            "minimum_observed_gap_m": observed["minimum_observed_through_gap_m"],
            "legal_immediate_hazard": "unassessed", "legal_yield": "unassessed"}


def measure_scope(observed):
    return {"case_id": observed["case_id"], "source_kind": observed["source_kind"],
            "control_exception": observed["controlling_exception"],
            "full_crossing_measured": observed["intersection_last_frame"] is not None}


def finalize(attempt, output):
    root = Path(attempt).resolve()
    target = Path(output)
    if target.exists():
        raise ValueError("Retain prior selected analysis output")
    config = json.loads(required(root, "config.json").read_text())
    case = config["selected_case_id"]
    required(root, "governing_sign.json")
    observed = inspect(root, case)
    public_observation = {key: value for key, value in observed.items() if key != "legal_verdict"}
    motion = rows(root, "stop_yield_motion.jsonl")
    frames = rows(root, "video_frames.jsonl")
    trace = rows(root, "trace.jsonl")
    if len(motion) != COUNT or len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError("Missing complete 600-frame saved source join")
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        path = required(root, name + ".mkv")
        count = subprocess.check_output(
            ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1",
             str(path)], text=True, timeout=120).strip()
        if count != str(COUNT):
            raise ValueError("Source camera decoded frame count differs: " + name)
    for index, (movement, frame, core) in enumerate(zip(motion, frames, trace)):
        native = movement["native_frame"]
        if (frame.get("video_frame") != index or frame.get("carla_frame") != native or
                core.get("frame") != native or
                abs(frame.get("time_s", -2) - movement["time_s"]) > 1e-6 or
                abs(core.get("time_s", -3) - movement["time_s"]) > 1e-6 or
                frame.get("source_cameras") != movement.get("source_cameras")):
            raise ValueError("Original Core/motion/video frame join differs")
        if observed["source_kind"] == "original_native_readback":
            hashes = frame.get("camera_rgb_sha256")
            if (not isinstance(hashes, dict) or set(hashes) != CAMERAS or
                    any(not isinstance(value, str) or len(value) != 64 for value in hashes.values())):
                raise ValueError("Original camera RGB source hash missing")
    if observed["source_kind"] == "original_native_readback":
        evidence = rows(root, "capture/evidence.jsonl")
        if len(evidence) != COUNT or any(evidence[i].get("original_frame") != motion[i]["native_frame"]
                                         for i in range(COUNT)):
            raise ValueError("Original Native evidence frame join differs")
        ego_bodies = rows(root, "ego_body.jsonl")
        through_bodies = rows(root, "through_body.jsonl")
        if len(ego_bodies) != COUNT or len(through_bodies) != COUNT:
            raise ValueError("Original actor body history incomplete")
        for i, (movement, subject, other) in enumerate(zip(motion, ego_bodies, through_bodies)):
            if (subject.get("native_frame") != movement["native_frame"] or
                    other.get("native_frame") != movement["native_frame"] or
                    subject.get("actor_id") != movement.get("ego_actor_id") or
                    other.get("actor_id") != movement.get("through_actor_id")):
                raise ValueError("Original actor body identity differs")
            ego_vertices = subject.get("body_vertices_m", [])
            other_vertices = other.get("body_vertices_m", [])
            if len(ego_vertices) < 4 or len(other_vertices) < 4:
                raise ValueError("Original actor body geometry missing")
            ego_center = (min(point[0] for point in ego_vertices) + max(point[0] for point in ego_vertices)) / 2
            through_center = (min(point[1] for point in other_vertices) + max(point[1] for point in other_vertices)) / 2
            ego_length = max(point[0] for point in ego_vertices) - min(point[0] for point in ego_vertices)
            through_length = max(point[1] for point in other_vertices) - min(point[1] for point in other_vertices)
            if (abs(ego_center - movement["ego_x_m"]) > .01 or
                    abs(through_center - movement["through_y_m"]) > .01 or
                    abs(ego_length - movement["ego_length_m"]) > .01 or
                    abs(through_length - movement["through_length_m"]) > .01):
                raise ValueError("Original actor body/motion geometry differs")
        map_hash = sha(required(root, "road.xodr"))
        for name in ("governing_sign.json", "stopping_reference.json", "governing_controls.json",
                     "through_road.json"):
            if json.loads(required(root, name).read_text()).get("map_readback_sha256") != map_hash:
                raise ValueError("Original map/control source hash differs: " + name)
    sources = {
        "stop": ["stop_yield_context.json", "stop_yield_motion.jsonl", "governing_sign.json"],
        "reference": ["stop_yield_context.json", "stop_yield_motion.jsonl", "stopping_reference.json"],
        "through": ["stop_yield_context.json", "stop_yield_motion.jsonl", "through_road.json",
                    "through_body.jsonl"],
        "scope": ["stop_yield_context.json", "stop_yield_motion.jsonl", "governing_controls.json"],
    }
    values = {
        "stop_sign_observation": ("measure_stop_sign", measure_stop_sign(observed), sources["stop"]),
        "reference_hierarchy_observation": ("measure_reference", measure_reference(observed), sources["reference"]),
        "through_highway_duty_observation": ("measure_through_duty", measure_through_duty(observed), sources["through"]),
        "control_scope_observation": ("measure_scope", measure_scope(observed), sources["scope"]),
    }
    measurements = {name: {"method": method, "value": value,
                           "sources": selected_sources(root, files)}
                    for name, (method, value, files) in values.items()}
    channel = root / "channels"
    channel.mkdir(exist_ok=True)
    (channel / "ego_stop_and_yield_sequence.jsonl").write_text("".join(
        json.dumps({"time_s": row["time_s"], "value": {
            "ego_x_m": row["ego_x_m"], "ego_speed_mps": row["ego_speed_mps"],
            "through_y_m": row["through_y_m"], "through_speed_mps": row["through_speed_mps"]}},
            allow_nan=False) + "\n" for row in motion))
    (channel / "ego_pose.jsonl").write_text("".join(
        json.dumps({"time_s": row["time_s"], "value": {"x_m": row["ego_x_m"],
                    "speed_mps": row["ego_speed_mps"]}}, allow_nan=False) + "\n"
        for row in motion))
    for channel_name, source_name in (("governing_control", "governing_controls.json"),
                                      ("stopping_reference_hierarchy", "stopping_reference.json"),
                                      ("through_highway", "through_road.json")):
        (channel / (channel_name + ".json")).write_text(json.dumps({
            channel_name: json.loads(required(root, source_name).read_text()),
            "source_sha256": sha(required(root, source_name))}, allow_nan=False) + "\n")
    result = {"case_id": case, "measured_values": public_observation,
              "target_checks": [{"target": "requested stop before reference",
                                 "requested": True,
                                 "measured": bool(observed["rest_frames_before_reference"]),
                                 "method": "saved original motion and stopping-reference geometry",
                                 "tolerance": "0.1 m/s is diagnostic only, not a legal threshold",
                                 "matched": bool(observed["rest_frames_before_reference"]),
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": ["stop_yield_motion.jsonl", "stop_yield_context.json"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "600 saved source frames measured; legal and physical review pending",
              "physical_failure_flags": ["original physical success not independently confirmed"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": [
                  {"name": "ego_pose", "unit": "m,deg", "reference": "channels/ego_pose.jsonl"},
                  {"name": "ego_stop_and_yield_sequence", "unit": "structured",
                   "reference": "channels/ego_stop_and_yield_sequence.jsonl"},
                  {"name": "governing_control", "unit": "structured",
                   "reference": "channels/governing_control.json"},
                  {"name": "stopping_reference_hierarchy", "unit": "structured",
                   "reference": "channels/stopping_reference_hierarchy.json"},
                  {"name": "through_highway", "unit": "structured",
                   "reference": "channels/through_highway.json"}],
              "realized_observables": {},
              "provenance_kind": "native" if observed["source_kind"] == "original_native_readback"
                                 else "synthetic_fixture",
              "diagnostic_fixture": observed["source_kind"] != "original_native_readback",
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    report = {"format": "nrs-484b-257-1-selected-analysis-v1", "case_id": case,
              "measurements": measurements, "analysis_complete": True,
              "source_kind": observed["source_kind"],
              "physical_acceptance_claimed": False,
              "limitations": ["Immediate hazard, statutory yield and physical success require original-source review."]}
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), allow_nan=False))
