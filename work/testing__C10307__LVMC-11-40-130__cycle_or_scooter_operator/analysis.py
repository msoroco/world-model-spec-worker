"""Saved-only selected bicycle speed and existing-condition finalizer.

Original sources are read through the SHA-bound acquisition inventory. This
report is descriptive and never decides reasonable or prudent speed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from speed_measurement import measure


ASSIGNMENT = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator"


def finalize(attempt: Path) -> dict:
    attempt = Path(attempt)
    for name in ("inventory.json", "frame-map.json", "bicycle-motion.json", "context.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__") or
            config.get("cell_id") != "C10307" or config.get("law_id") != "LVMC-11-40-130"):
        raise ValueError("saved bicycle case identity mismatch")
    inventory = json.loads((attempt / "inventory.json").read_text())
    measured = measure(attempt, inventory, case_id)
    provenance_path = attempt / "fixture-provenance.json"
    diagnostic = False
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text())
        diagnostic = (provenance.get("format") == "c10307-cpu-diagnostic-v1" and
                      provenance.get("case_id") == case_id and
                      provenance.get("physical_evidence") is False)
    if len(measured["samples"]) < (9 if diagnostic else 900):
        raise ValueError("Missing required source: full 900-frame original bicycle window")
    names = ("frame-map.json", "bicycle-motion.json", "context.json", "inventory.json")
    source_hashes = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest() for name in names}
    return {"format": "c10307-selected-bicycle-finalization-v1", "case_id": case_id,
            "measurements": {"actual_bicycle_speed_history": {"method": "measure_bicycle_speed",
                           "value": measured["samples"], "sources": source_hashes},
                             "contemporaneous_conditions": {"method": "measure_conditions",
                           "value": measured["condition_samples"], "sources": source_hashes}},
            "summary": measured["summary"], "source_sha256": source_hashes,
            "legal_prudence": "unresolved", "physical_acceptance": "unreviewed",
            "diagnostic_fixture": diagnostic}


def measure_bicycle_speed(attempt: Path) -> list:
    return finalize(attempt)["measurements"]["actual_bicycle_speed_history"]["value"]


def measure_conditions(attempt: Path) -> list:
    return finalize(attempt)["measurements"]["contemporaneous_conditions"]["value"]


def write_native_result(attempt: Path, report: dict) -> None:
    """Emit a saved result only when the original trace and all cameras exist.

    Synthetic fixture results explicitly leave every physical cause unconfirmed.
    """
    required = ("trace.jsonl", "video_frames.jsonl", "overview.mkv", "approach.mkv",
                "reference_corner.mkv", "driver_reference.mkv", "context.json")
    if any(not (attempt / name).is_file() for name in required):
        return
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    description = construction["recording_description"]
    if not isinstance(description, dict):
        raise ValueError("Native recording description is incomplete")
    samples = report["measurements"]["actual_bicycle_speed_history"]["value"]
    conditions = report["measurements"]["contemporaneous_conditions"]["value"]
    speed_path = attempt / "derived-bicycle-speed.jsonl"
    condition_path = attempt / "derived-conditions.jsonl"
    speed_path.write_text("".join(json.dumps({"time_s": row["time_s"], "value": row["speed_mps"]}) + "\n"
                                  for row in samples))
    condition_path.write_text("".join(json.dumps({"time_s": row["time_s"], "value": row}) + "\n"
                                      for row in conditions))
    commanded_path = attempt / "derived-commanded-target.json"
    commanded_path.write_text(json.dumps({"commanded_approach_speed": config["requested_speed_mps"]}) + "\n")
    evidence = [
        {"name": "actual_bicycle_speed", "unit": "m/s", "reference": speed_path.name},
        {"name": "contemporaneous_conditions", "unit": "structured", "reference": condition_path.name},
        {"name": "jurisdiction", "unit": "structured", "reference": "context.json"},
        {"name": "bicycle_classification", "unit": "structured", "reference": "context.json"},
        {"name": "commanded_approach_speed", "unit": "m/s", "reference": commanded_path.name},
    ]
    measured = report["summary"]["mean_speed_mps"]
    source_approach = report["summary"].get("approach_window", {}).get("source_verified") is True
    requested = config["requested_speed_mps"]
    tolerance = 0.25
    result = {"case_id": report["case_id"], "measured_values": report["summary"],
              "target_checks": [{"target": "bicycle_speed_mps", "requested": requested,
                                 "measured": measured,
                                 "method": ("saved original approach-window velocity magnitude mean"
                                            if source_approach else "saved diagnostic velocity magnitude mean"),
                                 "tolerance": tolerance, "matched": abs(requested - measured) <= tolerance,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": ("Original position/velocity join; independent physical review pending"
                                                    if source_approach else "Synthetic diagnostic shape only") }],
              "setup_confirmed": source_approach, "behavior_attempted": source_approach,
              "maneuver_completed": source_approach,
              "termination_reason": ("source-measured alley route complete; full capture elapsed"
                                     if source_approach else "diagnostic saved-source processing"),
              "physical_failure_flags": ["synthetic_fixture"] if report["diagnostic_fixture"] else ["physical_review_pending"],
              "trace_reference": "trace.jsonl", "video_references": list(required[2:6]),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {"commanded_approach_speed": {
                  "unit": "m/s", "method": "Read the commanded target from the frozen case controller and retain Native body velocity in the raw trace.",
                  "time_window": "The original 0 to 30 s capture window.", "statistic": "first",
                  "reference": commanded_path.name, "value": requested}},
              "diagnostic_fixture": report["diagnostic_fixture"]}
    output = attempt / "result.json"
    if output.exists():
        raise ValueError("refusing to overwrite saved Native result")
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite saved bicycle finalization")
    report = finalize(args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    write_native_result(args.attempt, report)


if __name__ == "__main__":
    main()
