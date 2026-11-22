"""Saved-only C136559 posted-speed measurement and Native result writer."""

import argparse
import hashlib
import json
from pathlib import Path

from posted_speed_measurements import analyze


CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def measure_peak_in_signed_zone(report):
    return report["peak_in_zone"]["measured_speed_mph"]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    for name in ("config.json", "trace.jsonl", "capture/evidence.jsonl", *CAMERAS):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if not case_id or not case_id.startswith("testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__"):
        raise ValueError("Wrong exact posted-speed case")
    if not config.get("recording_description"):
        raise ValueError("Missing recording description")
    report = analyze(attempt)
    peak = measure_peak_in_signed_zone(report)
    posted = report["posted_limit_mph"]
    target = config.get("requested_speed_mph")
    if type(target) not in (int, float) or target <= 0:
        raise ValueError("Missing requested speed")
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior finalization; choose a fresh attempt")
    speed_channel = attempt / "speed-channel.jsonl"
    channel_content = "".join(json.dumps({"time_s": sample["time_s"],
        "value": sample["measured_speed_mph"]}) + "\n" for sample in report["samples"])
    if speed_channel.exists():
        if speed_channel.read_text() != channel_content:
            raise ValueError("Prior derived speed channel differs from original sources")
    else:
        speed_channel.write_text(channel_content)
    result = {
        "case_id": case_id,
        "measured_values": {"sampled_peak_in_zone_mph": peak, "posted_limit_mph": posted,
                            "sampled_peak_greater_than_posted": report["sampled_peak_greater_than_posted"]},
        "target_checks": [{"target": "sampled_peak_in_zone_mph", "requested": target,
                           "measured": peak, "method": report["measurement_method"],
                           "tolerance": config.get("engineering_target_tolerance_mph", 0.5),
                           "matched": abs(peak - target) <= config.get("engineering_target_tolerance_mph", 0.5),
                           "physical_cause_confirmed": False,
                           "cause_evidence": ["subject_motion.jsonl", "sign_context.json"]}],
        "setup_confirmed": False, "behavior_attempted": True, "maneuver_completed": False,
        "termination_reason": "Saved source analysis; physical completion requires independent audit",
        "physical_failure_flags": ["authority and between-sample behavior unresolved"],
        "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": "kin.speed", "unit": "mph",
                                "reference": "speed-channel.jsonl"}],
        "source_hashes": report["sources"],
        "capture_evidence_sha256": _sha(attempt / "capture/evidence.jsonl"),
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    analysis = {"format": "worker-posted-speed-analysis", "case_id": case_id,
                "measurements": {"sampled_peak_in_zone_mph": {
                    "method": "measure_peak_in_signed_zone", "value": peak,
                    "sources": report["sources"]}},
                "source_report": report, "physical_checks": result["physical_checks"],
                "realized_observables": result["realized_observables"],
                "physical_acceptance_claimed": False}
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == "__main__":
    main()
