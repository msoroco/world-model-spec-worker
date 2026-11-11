"""Saved-only speed finalizer for the C10301 primary delivery case.

Reads original Native velocity, frame map and road context; writes a measured
result once. Never rewrites acquisition or treats requested speed as attainment.
"""

import argparse
import hashlib
import json
from pathlib import Path

from speed_measurements import analyze


CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def measure_peak_speed(report):
    return report["peak_sample"]["speed_mph"]


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(attempt: Path, output: Path) -> dict:
    from worker_exchange.native_output import write_result

    attempt, output = Path(attempt), Path(output)
    config_path = attempt / "config.json"
    if not config_path.is_file():
        raise ValueError("Missing required source: config.json")
    config = json.loads(config_path.read_text())
    for name in ("trace.jsonl", "capture/evidence.jsonl", *CAMERAS):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    report = analyze(attempt)
    if not config.get("selected_case_id") or not config.get("recording_description"):
        raise ValueError("Missing exact case or recording description")
    requested = config.get("requested_speed_mph")
    if isinstance(requested, bool) or not isinstance(requested, (int, float)) or requested <= 0:
        raise ValueError("Missing requested speed")
    speed = measure_peak_speed(report)
    sources = {name: report["sources"][name] for name in
               ("subject_motion.jsonl", "video_frames.jsonl", "road_context.json")}
    result = {
        "case_id": config["selected_case_id"],
        "measured_values": {"sampled_peak_speed_mph": speed,
                            "statutory_boundary_mph": 80.0},
        "target_checks": [{"target": "sampled_peak_speed_mph",
                           "requested": requested, "measured": speed,
                           "method": "original actor.get_velocity 3D magnitude",
                           "tolerance": config.get("engineering_target_tolerance_mph", 0.5),
                           "matched": abs(speed-requested) <= config.get("engineering_target_tolerance_mph", 0.5),
                           "physical_cause_confirmed": False,
                           "cause_evidence": ["subject_motion.jsonl", "video_frames.jsonl"]}],
        "setup_confirmed": False,
        "behavior_attempted": True,
        "maneuver_completed": False,
        "termination_reason": "saved source analysis; physical completion requires independent audit",
        "physical_failure_flags": ["road authority and between-sample peaks unresolved"],
        "trace_reference": "trace.jsonl",
        "video_references": list(CAMERAS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": {"source_hashes": sources,
                               "capture_evidence_sha256": _hash(attempt / "capture/evidence.jsonl")},
        "realized_observables": {"sampled_peak": report["peak_sample"],
                                 "sample_count": len(report["samples"]),
                                 "between_sample_peak": "unresolved",
                                 "road_public_way_judgment": "unresolved"},
    }
    analysis = {
        "format": "worker-speed-analysis",
        "case_id": config["selected_case_id"],
        "measurements": {
            "sampled_peak_speed_mph": {"method": "measure_peak_speed", "value": speed,
                                       "sources": sources}
        },
        "source_report": report,
    }
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior finalization; choose a fresh attempt")
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(Path(args.attempt), Path(args.output))


if __name__ == "__main__":
    main()
