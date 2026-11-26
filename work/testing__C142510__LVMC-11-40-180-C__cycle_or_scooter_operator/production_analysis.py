"""Saved-only original sidewalk, body-history and audio finalizer.

This finalizer measures source observations and leaves right-of-way and human
audibility for independent physical and legal review.
"""

import argparse
import hashlib
import json
from pathlib import Path

from sidewalk_overtake import measure


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root, name):
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("Missing required source: " + name)
    return target


def measure_original(attempt):
    for name in ("road.xodr", "site-context.json",
                 "rider-body-history.jsonl", "pedestrian-body-history.jsonl",
                 "emitter-event-history.jsonl", "pedestrian-microphone.wav"):
        required(Path(attempt), name)
    return measure(attempt)


def build(attempt):
    root = Path(attempt).resolve()
    config = json.loads(required(root, "config.json").read_text())
    site = json.loads(required(root, "site-context.json").read_text())
    if site.get("source_kind") != "original_native_capture" or not site.get(
            "reviewed_site_packet_sha256"):
        raise ValueError("reviewed original capture site provenance missing")
    observation = measure_original(root)
    if observation["case_id"] != config["selected_case_id"] or observation[
            "frame_count"] != 900:
        raise ValueError("original exact case differs")
    required(root, "trace.jsonl")
    required(root, "video_frames.jsonl")
    for name in VIEWS:
        required(root, name + ".mkv")
    source_names = tuple(observation["source_sha256"])
    sources = {name: hashlib.sha256(required(root, name).read_bytes()).hexdigest()
               for name in source_names}
    evidence = []
    source_for_channel = {
        "sidewalk_body_history": "rider-body-history.jsonl",
        "pedestrian_audio": "pedestrian-microphone.wav",
        "rider_response": "rider-body-history.jsonl",
        "camera_frame_identity": "video_frames.jsonl",
    }
    for channel in json.loads(required(root, "construction.json").read_text())[
            "recording_description"]["channels"]:
        name = channel["name"]
        if name not in source_for_channel:
            raise ValueError("unknown original sidewalk observation: " + name)
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": source_for_channel[name]})
    return ({"format": "worker-analysis-report",
             "case_id": observation["case_id"], "analysis_complete": True,
             "physical_acceptance_claimed": False,
             "legal_verdict_claimed": False,
             "measurements": {"sidewalk_overtake_signal": {
                 "method": "measure_original", "value": observation,
                 "sources": sources}},
             "limitations": ["Original motion and waveform are measured; yielding right of way and human audibility remain unresolved."]},
            {"case_id": observation["case_id"],
             "measured_values": observation,
             "target_checks": [{"target": "source-bound sidewalk overtake and emitter-audio join",
                                "requested": config["case"], "measured": observation,
                                "method": "measure_original", "tolerance": None,
                                "matched": False, "physical_cause_confirmed": False,
                                "cause_evidence": sources}],
             "setup_confirmed": False, "behavior_attempted": False,
             "maneuver_completed": False,
             "termination_reason": "independent original physical review pending",
             "physical_failure_flags": [],
             "trace_reference": "trace.jsonl",
             "video_references": [name + ".mkv" for name in VIEWS],
             "video_frame_map_reference": "video_frames.jsonl",
             "recording_description": json.loads(required(root, "construction.json").read_text())[
                 "recording_description"],
             "recording_evidence": evidence, "realized_observables": {},
             "diagnostic_fixture": False,
             "physical_acceptance_claimed": False,
             "legal_verdict_claimed": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain existing original analysis")
    report, native = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, native)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
