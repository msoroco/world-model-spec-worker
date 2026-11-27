"""Saved-only LVMC 11.52.300 measurements from sealed original acquisition."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from night_parking_measurement import measure as source_measure


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_night_parking(attempt):
    attempt = Path(attempt)
    source_manifest = attempt / "night-parking-sources.json"
    if not source_manifest.is_file():
        raise ValueError("Missing required source: night-parking-sources.json")
    manifest = json.loads(source_manifest.read_text())
    if manifest.get("format") != "night-parking-original-sources-v1":
        raise ValueError("wrong original parking source manifest")
    for item in manifest.get("sources", {}).values():
        path = attempt / item["path"]
        if not path.is_file():
            raise ValueError("Missing required source: " + item["path"])
    return source_measure(attempt, manifest)


def _recording_evidence(attempt, description, value):
    attempt = Path(attempt)
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    source_manifest = json.loads((attempt / "night-parking-sources.json").read_text())
    original = [json.loads(line) for line in (attempt / source_manifest["sources"]["trace"]["path"]).read_text().splitlines()]
    streams = {
        "original_body_state": [row["subject"] for row in original],
        "other_vehicle_body_state": [row["other_vehicle"] for row in original],
        "civil_time": [row["utc_time"] for row in original],
        "vehicle_classification": [value["transport_capable"], value["self_propelled"], value["vehicle_exclusions_checked"]],
        "parking_activity": [value["activity"]],
        "street_jurisdiction": [value["start_local"], value["end_local"]],
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in streams:
            raise ValueError("unknown parking channel: " + name)
        path = channels / (name + ".jsonl")
        values = streams[name]
        with path.open("x") as handle:
            for index, row in enumerate(original):
                sample = values[index] if len(values) == len(original) else values
                handle.write(json.dumps({"time_s": index / 20, "value": sample}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": str(path.relative_to(attempt))})
    context = {item["name"]: {"source_hashes": value["source_hashes"]} for item in description["context_inputs"]}
    if context:
        path = channels / "parking-context.json"
        path.write_text(json.dumps(context, allow_nan=False) + "\n")
        evidence.extend({"name": item["name"], "unit": item["unit"], "reference": str(path.relative_to(attempt))} for item in description["context_inputs"])
    return evidence


def finalize(attempt, output):
    attempt = Path(attempt)
    output = Path(output)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case_id = config["selected_case_id"]
    if case_id != construction["case_id"]:
        raise ValueError("selected case differs from materialized construction")
    value = measure_night_parking(attempt)
    description = construction["recording_description"]
    evidence = _recording_evidence(attempt, description, value)
    requested = config["parking_duration_s"]
    matched = abs(value["elapsed_s"] - requested) <= .051
    source_set = dict(value["source_hashes"], **{"night-parking-sources.json": _sha(attempt / "night-parking-sources.json")})
    physical = {
        "status": "met" if matched else "not_met",
        "method": "sealed 20 Hz original body, event and civil-time episode measurement",
        "intervals": [{"first_frame": value["first_frame"], "last_frame": value["last_frame"]}],
        "sources": source_set,
        "legal_verdict_claimed": False,
        "physical_causation_claimed": False,
    }
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text()) if (attempt / "acquisition-provenance.json").is_file() else {}
    kind = provenance.get("provenance_kind", "synthetic_fixture")
    result = {
        "case_id": case_id,
        "measured_values": value,
        "target_checks": [{"target": "continuous original street parking duration_s", "requested": requested,
                           "measured": value["elapsed_s"], "method": "original event/frame joined duration",
                           "tolerance": .051, "matched": matched,
                           "physical_cause_confirmed": False, "cause_evidence": source_set}],
        "setup_confirmed": matched,
        "behavior_attempted": matched,
        "maneuver_completed": matched,
        "termination_reason": "Saved original episode measured; legal and independent physical review pending",
        "physical_failure_flags": [],
        "trace_reference": "trace.jsonl",
        "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": evidence,
        "realized_observables": {},
        "physical_checks": {"setup": physical, "target": physical, "maneuver": physical},
        "provenance_kind": kind,
        "diagnostic_fixture": provenance.get("diagnostic_fixture", kind != "native"),
        "physical_acceptance_claimed": False,
    }
    result_path = attempt / "result.json"
    if result_path.exists():
        raise ValueError("retained result exists; saved processing needs a fresh stage")
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    report = {
        "format": "worker-analysis-report", "case_id": case_id,
        "measurements": {"nighttime_parking_episode": {"value": value, "method": "measure_night_parking",
                                                   "sources": {**{item["path"]: item["sha256"] for item in json.loads((attempt / "night-parking-sources.json").read_text())["sources"].values()},
                                                               "night-parking-sources.json": _sha(attempt / "night-parking-sources.json")}}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "provenance_kind": kind,
        "diagnostic_fixture": result["diagnostic_fixture"],
        "limitations": ["No legal verdict, carriage classification acceptance, pixel acceptance or canonical delivery is claimed."],
        "analysis_complete": True,
        "legal_verdict_claimed": False,
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == "__main__":
    main()
