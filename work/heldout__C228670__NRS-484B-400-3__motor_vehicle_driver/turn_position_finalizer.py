"""Finalize original frame-joined body geometry for a surveyed left turn."""

import argparse
import hashlib
import json
from pathlib import Path

from body_position import measure_frame
from route_survey import load_survey

ASSIGNMENT = "heldout__C228670__NRS-484B-400-3__motor_vehicle_driver"
CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
SOURCES = ("route_survey_original.json", "route_survey_capture_receipt.json",
           "body_corners_original.jsonl", "video_frames.jsonl",
           "trace.jsonl", *CAMERAS)
CHANNELS = ("approach_body_to_centerline", "entry_body_right_of_centerline",
            "departure_body_to_left_curb", "highway_directions")


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError("Missing required source: " + name)
    return path


def source_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(survey_path, survey_sha256, body_path, output_path):
    survey = load_survey(survey_path, survey_sha256)
    body_path = Path(body_path)
    if not body_path.is_file():
        raise ValueError("Missing original body stream")
    rows = [json.loads(line) for line in body_path.read_text().splitlines() if line]
    if not rows:
        raise ValueError("Empty original body stream")
    seen = set()
    phases = set()
    observations = []
    for row in rows:
        measured = measure_frame(row, survey)
        frame = measured["frame"]
        if frame in seen:
            raise ValueError("Duplicate original frame")
        seen.add(frame)
        phases.add(measured["phase"])
        observations.append(measured)
    if phases != {"approach", "entry", "departure"}:
        raise ValueError("Original turn phases are incomplete")
    if [x["frame"] for x in observations] != sorted(seen):
        raise ValueError("Original frame order changed")
    report = {
        "format": "worker-original-turn-position-measurement",
        "source": "Native XODR surveyed route and original full-body corners",
        "survey_sha256": survey_sha256,
        "original_body_path": body_path.name,
        "frames": len(observations),
        "phases": sorted(phases),
        "observations": observations,
        "legal_conclusion": None,
        "limitations": "Public highway status, directions, legal proximity and original camera visibility need source review",
    }
    Path(output_path).write_text(json.dumps(report, indent=2) + "\n")
    return report


def analyze_attempt(attempt, write_channels=True):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__") or
            config.get("law_id") != "NRS-484B-400-3" or config.get("cell_id") != "C228670" or
            config.get("actor") != "motor_vehicle_driver"):
        raise ValueError("Wrong exact two-way-to-one-way turn identity")
    source_paths = {name: required(root, name) for name in SOURCES}
    receipt = json.loads(source_paths["route_survey_capture_receipt.json"].read_text())
    expected = receipt.get("source_sha256")
    if (receipt.get("case_id") != case_id or
            receipt.get("source_path") != "route_survey_original.json" or
            not isinstance(expected, str) or len(expected) != 64):
        raise ValueError("Original Native route survey receipt is missing or stale")
    survey = load_survey(source_paths["route_survey_original.json"], expected)
    if receipt.get("map_name") != survey["map_name"] or receipt.get("native_route_verified") is not True:
        raise ValueError("Native route survey verification receipt is incomplete")
    body = source_rows(source_paths["body_corners_original.jsonl"])
    mapping = source_rows(source_paths["video_frames.jsonl"])
    trace = source_rows(source_paths["trace.jsonl"])
    if not body or not len(body) == len(mapping) == len(trace):
        raise ValueError("Original body, frame map and trace inventories differ")
    observations = []
    phases = set()
    for index, (original, frame_map, motion) in enumerate(zip(body, mapping, trace)):
        frame = original.get("frame")
        time_s = original.get("time_s")
        if (frame_map.get("video_frame") != index or frame_map.get("carla_frame") != frame or
                frame_map.get("time_s") != time_s or motion.get("frame") != frame or
                motion.get("time_s") != time_s):
            raise ValueError("Original body, frame map and trace join differs")
        measured = measure_frame(original, survey)
        measured["time_s"] = time_s
        observations.append(measured)
        phases.add(measured["phase"])
    if phases != {"approach", "entry", "departure"}:
        raise ValueError("Original turn phases are incomplete")
    if [row["frame"] for row in observations] != sorted({row["frame"] for row in observations}):
        raise ValueError("Original turn frames are duplicated or unordered")
    streams = {name: [] for name in CHANNELS}
    for row in observations:
        common = {"frame": row["frame"], "time_s": row["time_s"]}
        if row["phase"] == "approach":
            streams["approach_body_to_centerline"].append(dict(common, value={
                "signed_corner_offsets_m": row["approach_centerline_signed_corner_offsets_m"],
                "all_corners_right": row["all_corners_right_of_approach_centerline"]}))
        elif row["phase"] == "entry":
            streams["entry_body_right_of_centerline"].append(dict(common, value={
                "all_corners_right": row["all_corners_right_of_approach_centerline"],
                "signed_corner_offsets_m": row["approach_centerline_signed_corner_offsets_m"]}))
        elif row["phase"] == "departure":
            streams["departure_body_to_left_curb"].append(dict(common, value={
                "corner_distances_m": row["departure_left_curb_corner_distances_m"],
                "farthest_corner_m": row["farthest_body_corner_from_departure_left_curb_m"]}))
        streams["highway_directions"].append(dict(common, value={
            "approach_directions": survey["approach_directions"],
            "destination_directions": survey["destination_directions"],
            "map_name": survey["map_name"]}))
    if any(not stream for stream in streams.values()):
        raise ValueError("Mandatory original turn observation is empty")
    if write_channels:
        for name, stream in streams.items():
            channel = root / (name + ".jsonl")
            if channel.exists():
                raise ValueError("Derived turn channel already exists: " + name)
            channel.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in stream))
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {name: {"method": "analyze_attempt",
                                     "value": stream, "sources": {key: sha256(path) for key, path in source_paths.items()}}
                             for name, stream in streams.items()},
            "limitations": ["Native route survey provenance does not establish public highway access or legal proximity; original pixels need review."],
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def build_native_result(attempt, report):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text())
    description = config["case"]["recording_description"]
    units = {channel["name"]: channel["unit"] for channel in description["channels"]}
    evidence = []
    realized = {}
    for name in CHANNELS:
        channel = required(root, name + ".jsonl")
        stream = report["measurements"][name]["value"]
        evidence.append({"name": name, "unit": units[name], "reference": channel.name,
                         "sha256": sha256(channel)})
        realized[name] = {"unit": units[name], "method": "source-joined original turn geometry",
                          "time_window": "original turn frames", "statistic": "sample count",
                          "reference": channel.name, "value": len(stream),
                          "sample_window_s": [stream[0]["time_s"], stream[-1]["time_s"]]}
    return {"case_id": report["case_id"], "measured_values": {name: len(report["measurements"][name]["value"]) for name in CHANNELS},
            "target_checks": [{"target": "two-way-to-one-way left-turn geometry",
                               "requested": "original body approach, entry and departure against surveyed road geometry",
                               "measured": sum(len(report["measurements"][name]["value"]) for name in CHANNELS),
                               "method": "source-hashed Native route survey and frame-joined original body corners",
                               "tolerance": None, "matched": False, "physical_cause_confirmed": False,
                               "cause_evidence": "Original geometry measured; public access, pixels and legal proximity pending"}],
            "setup_confirmed": False, "behavior_attempted": True, "maneuver_completed": False,
            "termination_reason": "Saved original turn measured; physical and legal outcome unverified",
            "physical_failure_flags": {"visibility_validated": False},
            "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
            "video_frame_map_reference": "video_frames.jsonl", "recording_description": description,
            "recording_evidence": evidence, "realized_observables": realized,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey")
    parser.add_argument("--survey-sha256")
    parser.add_argument("--body")
    parser.add_argument("--attempt")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.attempt:
        report = analyze_attempt(args.attempt)
        output = Path(args.output)
        if output.exists():
            raise ValueError("Retain prior turn analysis report")
        output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        from worker_exchange.native_output import write_result
        write_result(args.attempt, build_native_result(args.attempt, report))
    else:
        if not (args.survey and args.survey_sha256 and args.body):
            parser.error("--survey, --survey-sha256 and --body required without --attempt")
        print(json.dumps({key: value for key, value in finalize(args.survey, args.survey_sha256, args.body, args.output).items() if key != "observations"}, sort_keys=True))
