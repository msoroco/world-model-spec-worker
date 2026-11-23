"""Saved-only proposed finalizer; original Native and video sources required.

This component has no CARLA import and makes no physical or legal acceptance
claim. The exact selected recipe and runtime process-saved binding remain work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_measurement import analyze


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decoded_frames(path: Path) -> int:
    if not path.is_file():
        raise ValueError("Missing original source camera: " + path.name)
    run = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                          "-show_entries", "stream=nb_read_frames", "-of",
                          "default=noprint_wrappers=1:nokey=1", str(path)],
                         text=True, capture_output=True, timeout=120)
    if run.returncode or not run.stdout.strip().isdigit():
        raise ValueError("Original source video decode failed: " + path.name)
    return int(run.stdout.strip())


def finalize(attempt: Path, output: Path) -> dict:
    attempt = attempt.resolve()
    output = output.resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior finalization; use a fresh attempt")
    config_path = attempt / "config.json"
    if not config_path.is_file():
        raise ValueError("Missing exact case configuration")
    config = json.loads(config_path.read_text())
    if config.get("assignment_id") != "training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator":
        raise ValueError("Assignment identity differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("Exact 30-second capture contract differs")
    if config.get("case_variant") not in ("two_cycles", "one_cycle"):
        raise ValueError("Unknown exact case variant")
    analysis = analyze(attempt)
    video_paths = [attempt / (name + ".mkv") for name in CAMERAS]
    counts = {path.name: decoded_frames(path) for path in video_paths}
    if any(count != 600 for count in counts.values()):
        raise ValueError("Original source camera frame count differs")
    observed = analysis["case_observation"]
    expected = config["case_variant"] == "two_cycles"
    matched = observed["two_cycles_before_entry"] == expected
    result = {
        "case_id": config["case_id"],
        "measured_values": {"signal_cycle_and_straight_entry": observed,
                            "other_device_prohibition_survey": analysis["other_device_prohibition_survey"]},
        "target_checks": [{"target": "two complete signal cycles before straight entry",
                           "requested": expected,
                           "measured": observed["two_cycles_before_entry"],
                           "method": "original Native phase transitions after measured full stop and before straight entry",
                           "tolerance": 0, "matched": matched,
                           "physical_cause_confirmed": False,
                           "cause_evidence": list(analysis["sources"])}],
        "setup_confirmed": False,
        "behavior_attempted": True,
        "maneuver_completed": False,
        "termination_reason": "Saved original-frame software measurement completed; physical and pixel review pending",
        "physical_failure_flags": ["physical_detector_causation_and_pixel_review_unverified"]
                                  + ([] if matched else ["controlled_cycle_target_mismatch"]),
        "trace_reference": "native_samples.jsonl",
        "video_references": [path.name for path in video_paths],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [
            {"name": "native_samples", "unit": "original Native frame", "reference": "native_samples.jsonl"},
            {"name": "video_frame_map", "unit": "original video frame", "reference": "video_frames.jsonl"}],
        "realized_observables": {
            "complete_cycles_before_entry": {"value": len([f for f in observed["complete_cycle_end_frames"]
                                                           if f < observed["entry_frame"]]),
                                             "unit": "complete observed device cycles",
                                             "method": "source-joined phase transition count",
                                             "time_window": "measured halt to straight entry",
                                             "statistic": "count", "reference": "native_samples.jsonl"}},
        "provenance_kind": "native_source_required",
        "accepted": False,
        "legal_verdict_claimed": False,
    }
    # Validate the same result shape expected by the pinned Native output
    # contract, without writing to the frozen runtime tree.
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {"format": "c111071-saved-finalizer-report-v1",
              "case_id": config["case_id"], "case_variant": config["case_variant"],
              "saved_analysis": analysis, "video_frame_counts": counts,
              "video_sha256": {path.name: sha(path) for path in video_paths},
              "config_sha256": sha(config_path),
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.mkdir(parents=True)
    (output / "saved-analysis.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
