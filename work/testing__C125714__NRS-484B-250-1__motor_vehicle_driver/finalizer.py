"""Saved-only median crossing measurement from retained Native sources."""
import argparse
import hashlib
import json
from pathlib import Path

from crossing_precedence import analyze

CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt: Path, output: Path) -> dict:
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain previous finalization; choose a fresh attempt")
    required = ("config.json", "junction_context.json", "crossing_history.jsonl",
                "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl", *CAMERAS)
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing original source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id", "")
    if not case_id.startswith("testing__C125714__NRS-484B-250-1__motor_vehicle_driver__"):
        raise ValueError("Exact C125714 subsection-1 case required")
    if config.get("law_id") != "NRS-484B-250-1" or config.get("cell_id") != "C125714":
        raise ValueError("Exact law and cell required")
    expected = config.get("expected_other_enters_before_ego")
    if type(expected) is not bool:
        raise ValueError("Explicit expected entry order required")
    physical = config.get("physical_completion", {})
    if "junction_context.json" not in physical.get("context_sources", []):
        raise ValueError("Pinned physical assessor must read sourced crossing polygon")
    if physical.get("body_key") != "ego_vertices_m":
        raise ValueError("Pinned physical assessor must read original ego body")
    description = config.get("recording_description")
    if not isinstance(description, dict):
        raise ValueError("Recording description required")
    report = analyze(attempt)
    sources = report["sources"]
    channels = attempt / "channels"
    if channels.exists():
        raise ValueError("Retain prior derived channels; choose a fresh attempt")
    channels.mkdir()
    for role in ("ego", "other"):
        with (channels / (role + "_inside.jsonl")).open("x") as stream:
            for sample in report["samples"]:
                stream.write(json.dumps({"time_s": sample["time_s"],
                                         "original_frame": sample["frame"],
                                         "value": int(sample[role + "_inside"])}) + "\n")
    context = {
        "format": "worker-median-crossing-measurements",
        "first_body_entry": report["first_body_entry"],
        "other_enters_before_ego": report["other_enters_before_ego"],
        "other_body_inside_at_ego_entry": report["other_body_inside_at_ego_entry"],
        "entry_time_difference_s": report["entry_time_difference_s"],
        "source_hashes": sources,
        "legal_conclusion": "unresolved",
    }
    (channels / "crossing_context.json").write_text(json.dumps(context, indent=2) + "\n")
    measured = report["other_enters_before_ego"]
    result = {
        "case_id": case_id,
        "measured_values": {
            "other_enters_before_ego": measured,
            "other_body_inside_at_ego_entry": report["other_body_inside_at_ego_entry"],
            "entry_time_difference_s": report["entry_time_difference_s"],
        },
        "target_checks": [{
            "target": "other_enters_before_ego", "requested": expected,
            "measured": measured, "method": "original complete-body entry at one sourced crossing",
            "tolerance": 0, "matched": measured is expected,
            "physical_cause_confirmed": False,
            "cause_evidence": ["crossing_history.jsonl", "junction_context.json",
                               "video_frames.jsonl"],
        }],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved original-source analysis; independent physical review pending",
        "physical_failure_flags": ["statutory crossing identity and yielding judgment unverified"],
        "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": [
            {"name": role + "_inside", "unit": "boolean sample",
             "reference": "channels/" + role + "_inside.jsonl"}
            for role in ("ego", "other")
        ] + [{"name": "crossing_context", "unit": "structured record",
              "reference": "channels/crossing_context.json"}],
        "source_evidence_hashes": sources,
        "capture_evidence_sha256": _sha(attempt / "capture/evidence.jsonl"),
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    analysis = {"format": "worker-median-crossing-saved-analysis",
                "case_id": case_id, "source_report": report,
                "measurements": context,
                "physical_acceptance_claimed": False}
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
