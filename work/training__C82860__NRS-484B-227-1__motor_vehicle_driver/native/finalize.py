"""Finalize a saved divided-road U-turn without assigning a legal outcome."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from measure_uturn import measure_attempt as _measure_attempt


def measure_attempt(attempt):
    """Selected contract entrypoint for the saved U-turn meter."""
    return _measure_attempt(attempt)

CAMERAS = ("overview", "approach", "median_reference", "driver_reference")
SOURCES = ("request.json", "divided-road-context.json", "source-review.json",
           "native-uturn.jsonl", "video_frames.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh saved analysis version")
    for name in ("config.json", "construction.json", "trace.jsonl",
                 "body_history.jsonl", "capture/evidence.jsonl", *SOURCES,
                 *(name + ".mkv" for name in CAMERAS)):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    request = json.loads((attempt / "request.json").read_text())
    case = request["case_id"]
    if config.get("selected_case_id") != case or construction.get("case_id") != case:
        raise ValueError("Exact saved case identity differs")
    measurement = measure_attempt(attempt)
    rows = [json.loads(line) for line in (attempt / "native-uturn.jsonl").read_text().splitlines()]
    context = json.loads((attempt / "divided-road-context.json").read_text())
    channels = attempt / "channels"
    channels.mkdir()
    values = {
        "ego_pose": lambda row: row["ego"],
        "median_crossing_location": lambda row: {
            "body_xy_m": row["ego"]["body_xy_m"],
            "roadways": context["native_roadways"],
            "median_bounds_m": context["median_bounds_m"],
            "opening_bounds_m": context["opening_bounds_m"],
            "source_frame": row["video_frame"],
        },
    }
    evidence = []
    for name, value in values.items():
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"], "value": value(row)},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": "structured", "reference": "channels/" + path.name})
    through_opening = measurement["opening_overlap_frames"] > 0
    outside_opening = measurement["median_without_opening_overlap_frames"] > 0
    target = request["case_id"].split("__")[-1]
    geometry_seen = through_opening if target == "authorized_opening" else outside_opening
    diagnostic = measurement["source_kind"] != "original_native"
    result = {
        "case_id": case, "measured_values": measurement,
        "target_checks": [{"target": "original divided-road body crossing",
                           "requested": target, "measured": measurement,
                           "method": "measure_attempt", "tolerance": {},
                           "matched": geometry_seen,
                           "physical_cause_confirmed": False,
                           "cause_evidence": list(SOURCES)}],
        "setup_confirmed": False,
        "behavior_attempted": not diagnostic,
        "maneuver_completed": False,
        "termination_reason": "600-frame geometry analyzed; original authority and physical review pending",
        "physical_failure_flags": ["Public-authority establishment, physical crossing and pixels require original review"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": construction["recording_description"],
        "recording_evidence": evidence, "realized_observables": {},
        "provenance_kind": "synthetic_local_diagnostic" if diagnostic else "native",
        "accepted": False,
    }
    for parent in (attempt, *attempt.parents):
        if (parent / "runtime" / "scenario_pipeline").is_dir():
            sys.path.insert(0, str(parent / "runtime"))
            break
    from scenario_pipeline.worker_exchange.native_output import write_result
    write_result(attempt, result)
    sources = {name: sha(attempt / name) for name in SOURCES}
    report = {"format": "worker-analysis-report", "case_id": case,
              "measurements": {name: {"method": "measure_attempt", "value": measurement,
                                       "sources": sources}
                               for name in ("right_hand_roadway", "divider_crossing",
                                            "u_turn_event", "opening_geometry", "authority_context")},
              "source_complete": True, "diagnostic_fixture": diagnostic,
              "physical_or_legal_acceptance": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
