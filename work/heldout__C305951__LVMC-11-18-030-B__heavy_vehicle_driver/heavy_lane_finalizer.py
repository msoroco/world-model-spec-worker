"""Saved-only heavy marked-lane measurement from retained original sources."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from heavy_lane_source import measure_footprint
from runner import CASE, check_config


CAMERA_FILES = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
                "driver_reference.mkv")


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError("Missing required source: " + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt, *, write_channels=True):
    root = Path(attempt)
    config_path, config_sha = _required(root, "config.json")
    config = check_config(json.loads(config_path.read_text()))
    survey_path, survey_sha = _required(root, "native_three_lane_survey.json")
    survey = json.loads(survey_path.read_text())
    if len(survey.get("lanes", [])) != 3:
        raise ValueError("Original source does not establish three lanes")
    frame_path, frame_sha = _required(root, "video_frames.jsonl")
    trace_path, trace_sha = _required(root, "trace.jsonl")
    body_path, body_sha = _required(root, "heavy_lane_sources.jsonl")
    video_hashes = {name: _required(root, name)[1] for name in CAMERA_FILES}
    frames, trace, body = _rows(frame_path), _rows(trace_path), _rows(body_path)
    if not frames or len(frames) > config["frames"] or not (
            len(frames) == len(trace) == len(body)):
        raise ValueError("Original heavy-lane source frame count differs")
    surveyed = {(lane["road_id"], lane["lane_id"]) for lane in survey["lanes"]}
    measured = []
    for index, (mapping, motion, observation) in enumerate(zip(frames, trace, body)):
        frame, time_s = mapping.get("carla_frame"), mapping.get("time_s")
        if (mapping.get("video_frame") != index or
                motion.get("frame") != frame or motion.get("time_s") != time_s or
                observation.get("frame") != frame or observation.get("time_s") != time_s):
            raise ValueError("Original heavy-lane body/trace/video frame join failed")
        if observation.get("survey_sha256") != survey_sha:
            raise ValueError("Original heavy-lane survey source hash differs")
        lane = observation["lane"]
        if (lane["road_id"], lane["lane_id"]) not in surveyed:
            raise ValueError("Original body left surveyed lane allocation")
        result = measure_footprint(observation)
        result["time_s"] = time_s
        measured.append(result)
    sources = {"native_three_lane_survey.json": survey_sha,
               "video_frames.jsonl": frame_sha, "trace.jsonl": trace_sha,
               "heavy_lane_sources.jsonl": body_sha, **video_hashes}
    values = {
        "native_lane_boundaries": [row["lane"] for row in body],
        "heavy_vehicle_footprint": [row["heavy_vehicle_components"] for row in body],
        "lane_boundary_overlap": [row["minimum_clearance_m"] for row in measured],
        "passing_context": [{"overtaken": row.get("overtaken"),
                             "exception_asserted": False} for row in body],
        "turn_preparation_context": [{"motion": motion,
                                      "lawful_turn_premise": None} for motion in trace],
        "four_camera_originals": [{"video_frame": index,
                                   "sources_sha256": video_hashes}
                                  for index in range(len(frames))],
    }
    if write_channels:
        for name, series in values.items():
            channel = root / (name + ".jsonl")
            if channel.exists():
                raise ValueError("Retain prior derived heavy-lane channel: " + name)
            channel.write_text("".join(json.dumps({"frame": frame["carla_frame"],
                                                   "time_s": frame["time_s"],
                                                   "value": value}, allow_nan=False) + "\n"
                                       for frame, value in zip(frames, series)))
    return {"format": "worker-analysis-report", "case_id": CASE,
            "measurements": {"heavy_lane_footprint": {
                "method": "analyze",
                "value": {"frames": measured,
                          "minimum_clearance_m": min(row["minimum_clearance_m"]
                                                     for row in measured),
                          "surveyed_lane_count": 3},
                "sources": sources}},
            "limitations": ["CPU source geometry does not establish physical marking visibility, municipal applicability or either legal exception."],
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    description = config["case"]["recording_description"]
    evidence = []
    for item in description["channels"]:
        path, digest = _required(root, item["name"] + ".jsonl")
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": path.name, "sha256": digest})
    measurement = report["measurements"]["heavy_lane_footprint"]["value"]
    minimum = measurement["minimum_clearance_m"]
    return {"case_id": CASE,
            "measured_values": {"heavy_lane_footprint": measurement},
            "target_checks": [{"target": "measured heavy body versus marked lane",
                               "requested": "original per-component signed clearance history",
                               "measured": minimum,
                               "method": "source-joined Native body corners and waypoint lane geometry",
                               "tolerance": None, "matched": False,
                               "physical_cause_confirmed": False,
                               "cause_evidence": "CPU source fixture only; physical marking review pending"}],
            "setup_confirmed": False, "behavior_attempted": True,
            "maneuver_completed": False,
            "termination_reason": "Saved heavy-lane source measurement complete; physical outcome unverified",
            "physical_failure_flags": {"detection_validated": False},
            "trace_reference": "trace.jsonl",
            "video_references": list(CAMERA_FILES),
            "video_frame_map_reference": "video_frames.jsonl",
            "recording_description": description,
            "recording_evidence": evidence,
            "realized_observables": {"heavy_lane_minimum_clearance_m": {
                "unit": "m", "method": "minimum original body-corner signed lane clearance",
                "time_window": "all original frames", "statistic": "min",
                "reference": "lane_boundary_overlap.jsonl", "value": minimum,
                "sample_window_s": [measurement["frames"][0]["time_s"],
                                    measurement["frames"][-1]["time_s"]]}},
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior heavy-lane analysis report")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == "__main__":
    main()
