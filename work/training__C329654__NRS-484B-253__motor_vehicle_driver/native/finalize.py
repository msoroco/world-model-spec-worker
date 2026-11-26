"""Finalize an immutable saved left-turn capture on the CPU.

The diagnostic measurements describe observed order. They make no legal
priority or physical acceptance claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from saved_measure import CAMERAS, analyze, read_rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def decode_frames(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError("Four-camera source decode failed: " + path.name)
    return int(result.stdout.strip())


def measure_yield_sequence(attempt, report):
    """Return source-bound actor order and post-yield response observations."""
    names = ("left-turn-actors.jsonl", "video_frames.jsonl",
             "camera-frames.jsonl", "road_geometry.json", "map-survey.json")
    hashes = {name: sha(required(attempt, name)) for name in names}
    measured = report["measured"]
    value = {key: measured[key] for key in (
        "first_turn_progress_frame", "first_opponent_conflict_frame",
        "subsequent_opponent_conflict_frame", "initial_opponent_passed_before_turn",
        "preturn_wait_observed", "turn_signal_observed_before_and_at_turn",
        "subsequent_yield_response_observed")}
    return {"value": value, "method": "measure_yield_sequence", "sources": hashes}


def source_join(attempt, report):
    actors = read_rows(required(attempt, "left-turn-actors.jsonl"))
    mapping = read_rows(required(attempt, "video_frames.jsonl"))
    trace = read_rows(required(attempt, "trace.jsonl"))
    evidence = read_rows(required(attempt, "capture/evidence.jsonl"))
    bodies = read_rows(required(attempt, "interaction_history.jsonl"))
    for index, (actor, frame, tr, ev, body) in enumerate(
            zip(actors, mapping, trace, evidence, bodies)):
        native = actor["native_frame"]
        if frame["native_frame"] != native or frame["video_frame"] != index or \
                tr["frame"] != native or ev["original_frame"] != native or \
                body["frame"] != native:
            raise ValueError("Saved original trace/evidence/body frame join differs")
        if any(abs(float(value) - actor["time_s"]) > 0.001 for value in (
                frame["time_s"], tr["time_s"], ev["recording_time_s"], body["time_s"])):
            raise ValueError("Saved original trace/evidence/body time join differs")
    road = json.loads(required(attempt, "road_geometry.json").read_text())
    survey = json.loads(required(attempt, "map-survey.json").read_text())
    survey_kind = survey.get("source_kind")
    if survey.get("format") == "c329654-original-map-survey-v1":
        survey_kind = "original_native"
    if road.get("source_kind") != report["source_kind"] or \
            survey_kind != report["source_kind"]:
        raise ValueError("Saved map and actor provenance differ")
    if not (road.get("intersection_polygon_xy_m") or road.get("intersection_xy_m")):
        raise ValueError("Missing source-bound intersection polygon")
    return {name: sha(required(attempt, name)) for name in (
        "trace.jsonl", "capture/evidence.jsonl", "interaction_history.jsonl",
        "road_geometry.json", "map-survey.json")}


def derive_channels(attempt, actors):
    channels = attempt / "channels"
    channels.mkdir(exist_ok=True)
    selectors = {"raw_ego_motion": lambda row: row["ego"],
                 "raw_oncoming_motion": lambda row: row["oncoming"],
                 "turn_signal_source": lambda row: {
                     "left_indicator_on": row["ego"]["left_indicator_on"],
                     "requested_controls": row.get("requested_controls")},
                 "four_camera_video": lambda row: {
                     "native_frame": row["native_frame"]}}
    for name, selector in selectors.items():
        path = channels / (name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"],
            "value": selector(row)}, allow_nan=False) + "\n" for row in actors))


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh saved attempt; original sources are immutable")
    config = json.loads(required(attempt, "config.json").read_text())
    if (config.get("rate_hz"), config.get("duration_s"),
            config.get("duration_frames")) != (20, 30, 600):
        raise ValueError("Exact 600-frame source window changed")
    saved = analyze(attempt)
    source_hashes = source_join(attempt, saved)
    videos = {name + ".mkv": decode_frames(required(attempt, name + ".mkv"))
              for name in CAMERAS}
    if any(count != 600 for count in videos.values()):
        raise ValueError("Four-camera 600-frame source incomplete")
    actors = read_rows(required(attempt, "left-turn-actors.jsonl"))
    derive_channels(attempt, actors)
    measured = saved["measured"]
    description = config.get("recording_description")
    if not isinstance(description, dict) or [item.get("name") for item in
            description.get("channels", [])] != ["raw_ego_motion",
            "raw_oncoming_motion", "turn_signal_source", "four_camera_video"]:
        raise ValueError("Frozen recording description differs")
    result = {"case_id": config["case_id"],
        "measured_values": {
            "initial_opponent_passed_before_turn":
                measured["initial_opponent_passed_before_turn"],
            "subsequent_opponent_decelerated_after_turn":
                measured["subsequent_opponent_decelerated_after_turn"],
            "first_turn_progress_frame": measured["first_turn_progress_frame"],
            "first_opponent_conflict_frame": measured["first_opponent_conflict_frame"]},
        "target_checks": [{"target": "observed left-turn yield sequence",
            "requested": config["yield_policy"],
            "measured": measured["initial_opponent_passed_before_turn"],
            "method": "saved original actor/frame joins", "tolerance": None,
            "matched": None, "physical_cause_confirmed": False,
            "cause_evidence": list(source_hashes)}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved 600-frame window analyzed; legal judgment separate",
        "physical_failure_flags": ["legal_immediate_hazard_and_signal_review_required"],
        "trace_reference": "trace.jsonl", "video_references": list(videos),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": [{"name": name, "unit": "structured",
            "reference": "channels/" + name + ".jsonl"}
            for name in ("raw_ego_motion", "raw_oncoming_motion",
                         "turn_signal_source", "four_camera_video")],
        "realized_observables": {}, "legal_verdict_claimed": False,
        "physical_acceptance_claimed": False}
    from worker_exchange.native_output import physical_result, validate_result
    physical_result(attempt, result)
    validate_result(result)
    measurement = measure_yield_sequence(attempt, saved)
    report = {"format": "c329654-left-turn-final-analysis-v1",
        "case_id": config["case_id"],
        "measurements": {"yield_sequence": measurement},
        "saved_analysis": saved, "original_source_hashes": source_hashes,
        "four_camera_frames": videos, "legal_verdict_claimed": False,
        "physical_acceptance_claimed": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2,
        allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
