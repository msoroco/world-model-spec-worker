"""Saved-only restricted-zone measurement finalizer; no legal verdict."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from saved_audit import audit as audit_saved


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _diagnostic(packet, case):
    if packet.get("case_id") != case or packet.get("source_kind") != "synthetic_fixture":
        raise ValueError("diagnostic zone source case/provenance mismatch")
    rows = packet.get("rows")
    if not isinstance(rows, list) or len(rows) != 9:
        raise ValueError("diagnostic zone source history incomplete")
    for index, row in enumerate(rows):
        if row.get("frame") != index or row.get("time_s") != index / 20:
            raise ValueError("diagnostic zone source frame join mismatch")
        for key in ("subject_station_m", "subject_speed_mps", "entrant_station_m",
                    "entrant_waiting", "entrant_access_blocked", "passenger_exchange_active",
                    "passenger_boarding_state", "entrant_parking_task_active"):
            if key not in row:
                raise ValueError("diagnostic zone observation missing: " + key)
    states = {row["passenger_boarding_state"] for row in rows}
    if not {"approaching", "boarding", "aboard"} <= states:
        raise ValueError("diagnostic passenger transition absent")
    return {"frame_count": 9, "subject_zone_dwell_frames": sum(
                10 <= row["subject_station_m"] <= 30 and row["subject_speed_mps"] < .1
                for row in rows),
            "passenger_exchange_frames": sum(bool(row["passenger_exchange_active"])
                                             for row in rows),
            "entrant_approach_frames": sum(row["entrant_station_m"] < 10 and
                                           row["entrant_parking_task_active"] for row in rows),
            "entrant_waiting_frames": sum(bool(row["entrant_waiting"]) for row in rows),
            "entrant_access_blocked_frames": sum(bool(row["entrant_access_blocked"])
                                                 for row in rows),
            "legal_interference": "unresolved_judgment"}


def build(attempt):
    attempt = Path(attempt)
    config = json.loads(required(attempt, "config.json").read_text())
    construction = json.loads(required(attempt, "construction.json").read_text())
    case = config["selected_case_id"]
    if construction["case_id"] != case:
        raise ValueError("restricted-zone construction mismatch")
    source = required(attempt, "original-attempt/site-packet.json")
    packet = json.loads(source.read_text())
    diagnostic = packet.get("diagnostic_fixture") is True
    if packet.get("case_id") != case:
        raise ValueError("restricted-zone source case mismatch")
    if diagnostic:
        measurement = _diagnostic(packet, case)
    else:
        trusted = os.environ.get("SCENARIO_RESTRICTED_ZONE_SITE_SHA256")
        if not trusted:
            raise ValueError("independent reviewed site hash required")
        measurement = audit_saved(attempt, case, trusted)["source_measurements"]
    videos = [name + ".mkv" for name in ("overview", "subject", "zone_access", "passenger_door")]
    for name in videos:
        required(attempt, name)
    trace = required(attempt, "trace.jsonl")
    mapping = required(attempt, "video_frames.jsonl")
    if len(trace.read_text().splitlines()) != len(mapping.read_text().splitlines()):
        raise ValueError("trace/video frame join missing")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    (channels / "zone.jsonl").write_text(json.dumps({"time_s": 0,
        "value": measurement}, sort_keys=True) + "\n")
    (channels / "context.json").write_text(json.dumps({"reviewed_restricted_zone": {
        "source_sha256": _sha(source),
        "review_status": "synthetic fixture" if diagnostic else "original source reviewed separately"}},
        sort_keys=True) + "\n")
    sources = {"original-attempt/site-packet.json": _sha(source)}
    report = {"format": "worker-analysis-report", "case_id": case,
              "analysis_complete": True, "legal_verdict_claimed": False,
              "measurements": {"restricted_zone_entrant_observations": {
                  "value": measurement, "method": "build", "sources": sources}},
              "limitations": ["Physical visibility and statutory judgments require independent review."]}
    result = {"case_id": case, "measured_values": measurement,
              "target_checks": [{"target": "restricted-purpose entrant during passenger exchange",
                                 "requested": config["scenario_parameters"],
                                 "measured": measurement, "method": "build",
                                 "tolerance": None, "matched": False,
                                 "physical_cause_confirmed": False, "cause_evidence": sources}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "physical and legal review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": videos, "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": [{"name": "subject_zone_dwell", "unit": "s",
                                      "reference": "channels/zone.jsonl"},
                                     {"name": "passenger_exchange", "unit": "state",
                                      "reference": "channels/zone.jsonl"},
                                     {"name": "entrant_access", "unit": "state",
                                      "reference": "channels/zone.jsonl"},
                                     {"name": "reviewed_restricted_zone", "unit": "source record",
                                      "reference": "channels/context.json"}],
              "realized_observables": {},
              "provenance_kind": "synthetic_fixture" if diagnostic else "native",
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False}
    return report, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite restricted-zone analysis")
    report, result = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
