"""Saved-only school-crossing measurement from source-joined Native packets.

This finalizer does not decide whether the School-Xing sign was actually legible,
the City authorized it, or the observed walker intended to cross. Independent
physical and semantic review remains mandatory after a real capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from saved_source import CAMERAS, EXPECTED_FRAMES, audit_case, sha, source


def measure_marking_context(attempt: Path, measured: dict) -> dict:
    geometry = json.loads(source(attempt, "road_geometry.json").read_text())
    return {"value": {"crosswalk_width_m": geometry["crosswalk"]["width_along_road_m"],
                      "sign_advance_m": measured["sign_advance_m"],
                      "native_map_object_present": True,
                      "city_authority_verified": False,
                      "actual_marking_pixels_verified": False},
            "method": "measure_marking_context",
            "sources": {name: sha(source(attempt, name)) for name in
                        ("road_geometry.json", "native_samples.jsonl")}}


def measure_signed_entry(attempt: Path, measured: dict) -> dict:
    return {"value": {"entry": measured["entry"],
                      "ego_rear_cleared_crosswalk": measured["ego_rear_cleared_crosswalk"],
                      "intent_from_motion_only": True,
                      "actual_sign_pixels_verified": False},
            "method": "measure_signed_entry",
            "sources": {name: sha(source(attempt, name)) for name in
                        ("road_geometry.json", "native_samples.jsonl",
                         "video_frames.jsonl")}}


def measure_reviewed_scope(attempt: Path, measured: dict) -> dict:
    return {"value": {"original_vehicle_entry_frame": measured["entry"]["native_frame"],
                      "person_in_crosswalk_on_approach_side": (
                          measured["entry"]["person_in_crosswalk"] and
                          measured["entry"]["person_on_approach_side"]),
                      "legal_outcome_claimed": False},
            "method": "measure_reviewed_scope",
            "sources": {name: sha(source(attempt, name)) for name in
                        ("native_samples.jsonl", "video_frames.jsonl")}}


def decoded_frames(path: Path) -> int:
    completed = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise ValueError("Original camera video decode failed: " + path.name)
    return int(completed.stdout.strip())


def derive_channels(attempt: Path, config: dict) -> None:
    native = [json.loads(line) for line in source(attempt, "native_samples.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in source(attempt, "video_frames.jsonl").read_text().splitlines()]
    geometry = json.loads(source(attempt, "road_geometry.json").read_text())
    folder = attempt / "channels"
    folder.mkdir(exist_ok=True)
    for channel in config["recording_description"]["channels"]:
        name = channel["name"]
        target = folder / (name + ".jsonl")
        if target.exists():
            raise ValueError("Retain original channel source: " + name)
        rows = []
        for sample, joined in zip(native, mapping):
            if name == "ego_front_entry":
                value = {"front_x_m": max(p[0] for p in sample["ego_body_xy_m"]),
                         "body_xy_m": sample["ego_body_xy_m"]}
            elif name == "person_crosswalk_sign":
                value = {"person": sample["person"], "geometry": geometry,
                         "sign_pixels_verified": False}
            elif name == "four_camera_video":
                value = {"native_frame": joined["native_frame"],
                         "camera_frames": joined["camera_frames"]}
            else:
                raise ValueError("Unknown school-crossing source channel: " + name)
            rows.append({"time_s": sample["time_s"], "value": value})
        target.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))


def finalize(attempt: Path, output: Path) -> dict:
    attempt = attempt.resolve()
    output = output.resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved result; use a fresh version")
    config = json.loads(source(attempt, "config.json").read_text())
    measured = audit_case(attempt, config["case_id"])
    videos = [name + ".mkv" for name in CAMERAS]
    video_counts = {name: decoded_frames(source(attempt, name)) for name in videos}
    if any(count != EXPECTED_FRAMES for count in video_counts.values()):
        raise ValueError("Original four-camera video duration differs")
    derive_channels(attempt, config)
    marking = measure_marking_context(attempt, measured)
    entry = measure_signed_entry(attempt, measured)
    reviewed_scope = measure_reviewed_scope(attempt, measured)
    wanted = config["condition"] == "entry_during_crossing"
    observed = (measured["entry"]["person_in_crosswalk"] is True and
                measured["entry"]["person_on_approach_side"] is True and
                measured["entry"]["person_approach_motion_observed"] is True)
    recording = []
    channels = config["recording_description"]["channels"]
    for channel in channels:
        name = channel["name"]
        recording.append({"name": name, "unit": channel["unit"],
                          "reference": "channels/" + name + ".jsonl"})
    result = {"case_id": config["case_id"],
        "measured_values": {"school_marking": marking["value"],
                            "signed_entry": entry["value"],
                            "reviewed_scope": reviewed_scope["value"]},
        "target_checks": [{"target": "same_side_person_present_at_entry",
            "requested": wanted, "measured": observed,
            "method": "saved original front-footprint and pedestrian frame join",
            "tolerance": 0, "matched": observed == wanted,
            "physical_cause_confirmed": False,
            "cause_evidence": ["road_geometry.json", "native_samples.jsonl",
                               "video_frames.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": True,
        "maneuver_completed": measured["ego_rear_cleared_crosswalk"],
        "termination_reason": "full original 600-frame source window retained",
        "physical_failure_flags": [
            "sign_pixels_city_authority_and_person_intent_require_independent_review"],
        "trace_reference": "trace.jsonl", "video_references": videos,
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": recording,
        "realized_observables": {"school_crosswalk_entry_frame": {
            "value": measured["entry"]["native_frame"], "unit": "Native frame",
            "method": "source-joined original ego front footprint",
            "time_window": "entire 30 s original attempt", "statistic": "first",
            "reference": "native_samples.jsonl"}},
        "provenance_kind": "synthetic_fixture" if measured["diagnostic_fixture"] else "native",
        "accepted": False,
        "legal_verdict_claimed": False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {"format": "worker-analysis-report", "case_id": config["case_id"],
              "measurements": {"school_marking_context": marking,
                               "signed_school_crossing_entry": entry,
                               "reviewed_school_entry": reviewed_scope},
              "original_source_hashes": measured["sources"],
              "source_video_frames": video_counts,
              "analysis_complete": True,
              "diagnostic_fixture": measured["diagnostic_fixture"],
              "physical_acceptance_claimed": False,
              "limitations": ["Original source joins and video frames establish measured motion only; displayed sign pixels, official marking authority and person intent remain unverified"]}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
