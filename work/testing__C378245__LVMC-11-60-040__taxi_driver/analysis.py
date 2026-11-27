"""Saved taxi source finalizer with explicit source and case joins.

This records measured geometry and independently reviewed activity. It never
decides whether a passenger exchange was legally expeditious.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from taxi_stand_measurement import ASSIGNMENT, measure


def source(attempt: Path, name: str) -> Path:
    path = attempt / name
    if not path.is_file() or not path.resolve().is_relative_to(attempt.resolve()):
        raise ValueError("Missing required source: " + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_stand_context(observation: dict) -> dict:
    return {"all_halt_footprints_inside_designated_stand":
            observation["all_halt_footprints_inside_designated_stand"],
            "all_halt_footprints_outside_designated_stand":
            observation["all_halt_footprints_outside_designated_stand"],
            "source_sha256": observation["source_sha256"]}


def measure_standing_or_parking(observation: dict) -> dict:
    return {"reviewed_activity": observation["reviewed_activity"],
            "halt_interval_frames": observation["halt_interval_frames"],
            "max_halt_speed_mps": observation["max_halt_speed_mps"],
            "footprints_outside_stand":
            observation["all_halt_footprints_outside_designated_stand"]}


def measure_passenger_exception(observation: dict) -> dict:
    return {"reviewed_activity": observation["reviewed_activity"],
            "passenger_event_kinds": observation["passenger_event_kinds"],
            "halt_interval_frames": observation["halt_interval_frames"],
            "expeditiousness_review_required": True,
            "other_regulation_review_required": True}


def analyze(attempt: Path, output: Path) -> dict:
    attempt = attempt.resolve()
    packet_path = source(attempt, "taxi-source-packet.json")
    packet = json.loads(packet_path.read_text())
    case_id = packet.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("Exact taxi case identity required")
    config = json.loads(source(attempt, "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("Saved taxi case differs from selected construction")
    for name in ("native_frames.json", "activity_review.json", "reviewed_site.json",
                 "native_result.json", "stand_designation.json", "taxi_licence.json",
                 "other_regulations.json"):
        source(attempt, name)
    observation = measure(packet, attempt)
    method_specs = [("taxi_stand_context", measure_stand_context),
                    ("taxi_halt_activity", measure_standing_or_parking)
                    if case_id.endswith(("__designated_stand_park", "__outside_stand_park",
                                         "__outside_stand_stand"))
                    else ("taxi_passenger_exception", measure_passenger_exception)]
    inputs = ["taxi-source-packet.json", "native_frames.json", "activity_review.json",
              "reviewed_site.json", "native_result.json", "stand_designation.json",
              "taxi_licence.json", "other_regulations.json"]
    hashes = {name: sha(source(attempt, name)) for name in inputs}
    report = {"format": "worker-taxi-source-analysis", "case_id": case_id,
              "measurements": {key: {"method": method.__name__, "value": method(observation),
                                     "sources": hashes}
                               for key, method in method_specs},
              "observation": observation,
              "legal_verdict": None,
              "scope": "Saved source measurements; legal expeditiousness and original authenticity require independent acceptance"}
    if output.name != "analysis-report.json":
        raise ValueError("Analysis output must be analysis-report.json")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    analyze(args.attempt, args.output)
