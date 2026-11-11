"""Saved-only subsection-2 entry analysis; physical/legal acceptance stays open."""
import argparse
import hashlib
import json
from pathlib import Path

from entry_measurements import analyze

CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")
PREFIX = "testing__C125714__NRS-484B-250-2__motor_vehicle_driver__"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measurement(report):
    """Keep measurements and legal uncertainty together with original hashes."""
    return {
        "method": "first complete Native body intersection with sourced crossing polygon",
        "first_body_entry": report["first_body_entry"],
        "ego_minus_other_entry_time_s": report["ego_minus_other_entry_time_s"],
        "other_is_to_ego_right": report["other_is_to_ego_right"],
        "geometric_yield_candidate": report["geometric_yield_candidate"],
        "approximately_same_time_judgment": "unresolved; no numeric legal threshold",
        "right_of_way_judgment": "unresolved",
        "source_hashes": report["sources"],
    }


def finalize(attempt: Path, output: Path):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior finalization; choose a fresh attempt")
    required = ("config.json", "road_geometry.json", "crossing_history.jsonl",
                "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl", *CAMERAS)
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id", "")
    if not case_id.startswith(PREFIX) or config.get("law_id") != "NRS-484B-250-2" or config.get("cell_id") != "C125714":
        raise ValueError("Exact C125714 subsection-2 case required")
    if not isinstance(config.get("recording_description"), dict):
        raise ValueError("Recording description required")
    report = analyze(attempt)
    if not all(report["first_body_entry"].values()):
        raise ValueError("Both participants must have original body entry measurements")
    channels = attempt / "channels"
    channels.mkdir()
    payload = measurement(report)
    (channels / "entry_context.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    result = {
        "case_id": case_id,
        "measured_values": {"entry_delta_s": report["ego_minus_other_entry_time_s"],
                            "other_is_to_ego_right": report["other_is_to_ego_right"]},
        "target_checks": [{
            "target": "both_bodies_enter_sourced_crossing", "requested": True,
            "measured": True, "method": payload["method"], "tolerance": 0,
            "matched": True, "physical_cause_confirmed": False,
            "cause_evidence": ["crossing_history.jsonl", "road_geometry.json", "video_frames.jsonl"],
        }],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved original-source entry analysis; physical and legal review pending",
        "physical_failure_flags": ["statutory crossing identity, approximate time, control devices and yielding unverified"],
        "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": "entry_context", "unit": "structured record",
                                "reference": "channels/entry_context.json"}],
        "source_evidence_hashes": report["sources"],
        "capture_evidence_sha256": _sha(attempt / "capture/evidence.jsonl"),
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    output.write_text(json.dumps({"format": "worker-median-entry-saved-analysis",
                                  "case_id": case_id, "measurement": payload,
                                  "physical_acceptance_claimed": False}, indent=2,
                                 allow_nan=False) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
