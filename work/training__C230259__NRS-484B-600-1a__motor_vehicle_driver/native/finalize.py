"""Saved-only exact speed/condition source join, without a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from conditions_source_v2 import measure

SOURCES = ("native_motion.jsonl", "conditions.jsonl", "video_frames.jsonl",
           "trace.jsonl", "capture/evidence.jsonl", "road.xodr")
VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved result; use a fresh attempt")
    for name in (*SOURCES, *VIDEOS, "config.json", "construction.json", "acquisition-provenance.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case = config.get("selected_case_id")
    aid = config.get("assignment_id")
    if case != construction.get("case_id") or case not in {aid + "__" + str(v) for v in (8, 12, 16, 20)}:
        raise ValueError("Saved exact-case identity differs")
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    diagnostic = provenance.get("diagnostic_fixture") is True
    source_kind = "synthetic_cpu_fixture" if diagnostic else "original_native"
    conditions = [json.loads(line) for line in (attempt / "conditions.jsonl").read_text().splitlines()]
    measured = measure(conditions, source_kind=source_kind)
    road_sha = sha(attempt / "road.xodr")
    if any(row["road"]["native_map_sha256"] != road_sha for row in conditions):
        raise ValueError("Native map source differs from condition rows")
    frame_map = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    motion = [json.loads(line) for line in (attempt / "native_motion.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
    if not (len(frame_map) == len(motion) == len(trace) == 600):
        raise ValueError("Full source frame and trace join required")
    for i, (frame, native, position, condition) in enumerate(zip(frame_map, motion, trace, conditions)):
        if (frame.get("video_frame") != i or native.get("video_frame") != i or
                native.get("native_frame") != frame.get("carla_frame") or
                condition.get("native_frame") != frame.get("carla_frame") or
                position.get("frame") != frame.get("carla_frame")):
            raise ValueError("Saved Native frame identities differ")
        if any(abs(row.get("time_s", -1) - condition["time_s"]) > 1e-5 for row in (frame, native, position)):
            raise ValueError("Saved Native timestamps differ")
        velocity = [native["velocity_x_mps"], native["velocity_y_mps"], native["velocity_z_mps"]]
        if any(abs(a-b) > 1e-5 for a, b in zip(velocity, condition["ego_velocity_xyz_mps"])):
            raise ValueError("Native motion and condition velocity sources differ")
    hashes = {name: sha(attempt / name) for name in SOURCES}
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for index, row in enumerate(measured["frame_measurements"]):
                value = (row["ego_speed_mps"] if name == "measured_speed" else
                         trace[index]["position_m"] if name == "ego_pose" else row)
                stream.write(json.dumps({"time_s": row["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": "channels/" + path.name})
    camera_context = {"four_source_cameras": {name: sha(attempt / name) for name in VIDEOS}}
    (channels / "four_source_cameras.json").write_text(json.dumps(camera_context) + "\n")
    evidence.append({"name": "four_source_cameras", "unit": "video",
                     "reference": "channels/four_source_cameras.json"})
    context_value = {k: v for k, v in measured.items() if k != "frame_measurements"}
    # A controller target is an engineering request, never a legal speed limit.
    # Compare only source-measured speed with that request; a CPU fixture does
    # not establish that the physical cause or road conditions were realized.
    measured_speed = measured["ego_speed_mps"]["mean"]
    requested_speed = config["requested_speed_mps"]
    speed_tolerance_mps = 0.5
    report = {"format": "worker-analysis-report", "case_id": case,
              "measurements": {key: {"method": "finalize", "value": context_value, "sources": hashes}
                               for key in ("statutory_actor_context", "speed_conditions",
                                           "traffic_scope", "highway_conditions", "weather_conditions")},
              "source_complete": True, "diagnostic_fixture": diagnostic,
              "physical_or_legal_acceptance": False}
    result = {"case_id": case, "measured_values": measured,
              "target_checks": [{"target": "source-joined speed and conditions captured",
                                 "requested": requested_speed,
                                 "measured": measured_speed,
                                 "method": "measure_original_native_velocity_mean",
                                 "tolerance": speed_tolerance_mps,
                                 "matched": abs(measured_speed - requested_speed) <= speed_tolerance_mps,
                                 "physical_cause_confirmed": False, "cause_evidence": list(SOURCES)}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved sources measured; physical and legal review pending",
              "physical_failure_flags": ["Actual conditions and reasonableness unreviewed"],
              "trace_reference": "trace.jsonl", "video_references": list(VIDEOS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "provenance_kind": "synthetic_local_diagnostic" if diagnostic else "original_source_review",
              "accepted": False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
