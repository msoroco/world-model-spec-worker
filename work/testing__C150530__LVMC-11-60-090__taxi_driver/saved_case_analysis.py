"""Build case-specific measurements from a sealed original Native trace.

This source-join report is an engineering diagnostic. Documentary authenticity
and physical camera visibility require separate review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from turn_trace_finalizer import ASSIGNMENT, finalize


def _source(attempt: Path, name: str) -> Path:
    path = attempt / name
    if not path.is_file() or not path.resolve().is_relative_to(attempt.resolve()):
        raise ValueError("Missing required source: " + name)
    return path


def _hashes(attempt: Path, names: list[str]) -> dict[str, str]:
    return {name: hashlib.sha256(_source(attempt, name).read_bytes()).hexdigest()
            for name in names}


def measure_cab_stand_context(measured: dict, packet: dict) -> dict:
    return {"stand_departure_frame": measured["stand_departure_frame"],
            "sources": {key: measured["context_source_joins"][key]
                        for key in ("cab_license", "stand_designation", "stand_marking",
                                    "designation_provisions", "jurisdiction")}}


def measure_posted_notice_context(measured: dict, packet: dict) -> dict:
    return {"notice_meaning": packet["notice_meaning"],
            "notice_source": measured["context_source_joins"]["posted_notice"]}


def measure_first_intersection_maneuver(measured: dict, packet: dict) -> dict:
    return {key: measured[key] for key in
            ("stand_departure_frame", "first_intersection_entry_frame",
             "first_intersection_exit_frame", "first_junction_road_id",
             "receiving_road_id", "turn_angle_deg",
             "engineering_right_turn_observed")}


def analyze(attempt: Path, output: Path) -> dict:
    names = ("reviewed-context.json", "original-trace.jsonl",
             "original-trace-seal.json")
    paths = {name: _source(attempt, name) for name in names}
    packet = json.loads(paths["reviewed-context.json"].read_text())
    case_id = packet.get("case_id", "")
    case = case_id.removeprefix(ASSIGNMENT + "__")
    if (case_id != ASSIGNMENT + "__" + case or case not in
            ("near_stand", "far_stand", "near_stand_straight")):
        raise ValueError("Unknown exact case in reviewed context")
    root = Path(__file__).resolve().parent
    measured = finalize(paths["original-trace.jsonl"],
                        paths["original-trace-seal.json"],
                        paths["reviewed-context.json"],
                        root / "candidates" / (case + ".xodr"),
                        root / "candidates" / (case + ".json"), attempt)
    requirements = (
        ("cab_stand_context", measure_cab_stand_context,
         ["reviewed-context.json", "original-trace.jsonl", "original-trace-seal.json"]),
        ("posted_notice_context", measure_posted_notice_context,
         ["reviewed-context.json"]),
        ("first_intersection_maneuver", measure_first_intersection_maneuver,
         ["reviewed-context.json", "original-trace.jsonl", "original-trace-seal.json"]),
    )
    report = {"format": "c150530-saved-case-analysis-v1", "case_id": case_id,
              "measurements": {key: {"method": method.__name__,
                                     "value": method(measured, packet),
                                     "sources": _hashes(attempt, inputs)}
                               for key, method, inputs in requirements},
              "limitation": "Synthetic CPU attempts do not establish original documentary or physical truth"}
    if output.name != "analysis-report.json":
        raise ValueError("Analysis output must be analysis-report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == "__main__":
    main()
