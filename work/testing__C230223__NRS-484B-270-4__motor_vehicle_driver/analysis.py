"""Saved-only cycle-lane measurement; diagnostic fixtures remain diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT
from cycle_lane_original import _intersects, _polygon, audit as audit_original


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_saved(attempt: Path, case_id: str) -> tuple[dict, dict, bool]:
    config = json.loads((attempt / "config.json").read_text())
    if case_id != config["selected_case_id"] or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("saved exact case identity differs")
    required = ("site-source.json", "history.json", "subsection_3-source.json")
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    sources = {name: sha(attempt / name) for name in required}
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    diagnostic = provenance.get("diagnostic_fixture") is True
    if diagnostic:
        site = json.loads((attempt / "site-source.json").read_text())
        exception = json.loads((attempt / "subsection_3-source.json").read_text())
        if (site.get("diagnostic_fixture") is not True or
                exception.get("diagnostic_fixture") is not True or
                exception.get("status") != config["requested_subsection_3_status"]):
            raise ValueError("diagnostic source provenance or exact exception differs")
        rows = json.loads((attempt / "history.json").read_text())
        if not isinstance(rows, list) or len(rows) != 900:
            raise ValueError("900 diagnostic history frames required")
        intersection = _polygon(site["intersection_polygon"])
        lane = _polygon(site["cycle_lane_polygon"])
        for i, row in enumerate(rows):
            body = _polygon(row.get("ego_body_polygon"))
            if (row.get("frame") != i or abs(row.get("time_s", -1) - i / 20) > 0.001 or
                    row.get("ego_body_in_intersection") is not _intersects(body, intersection) or
                    row.get("ego_body_in_designated_cycle_lane") is not _intersects(body, lane)):
                raise ValueError("diagnostic frame/body/source join failed")
        measurement = {"frame_count": 900,
                       "intersection_cycle_lane_overlap_frames": sum(
                           row["ego_body_in_intersection"] and
                           row["ego_body_in_designated_cycle_lane"] for row in rows),
                       "subsection_3_status": exception["status"],
                       "source_kind": "synthetic_cpu_fixture"}
    else:
        reviewed = os.environ.get("C230223_REVIEWED_PACKET")
        if not reviewed:
            raise ValueError("independent reviewed original source hashes required")
        packet = json.loads(Path(reviewed).read_text())
        hashes = packet.get("reviewed_sha256", {})
        measurement = audit_original(attempt, hashes.get("site"),
                                     hashes.get("subsection_3"), hashes.get("vehicle"))
    return measurement, sources, diagnostic


def analyze(attempt: Path, case_id: str) -> dict:
    value, sources, diagnostic = measure_saved(attempt, case_id)
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {"cycle_lane_intersection_observation": {
                "value": value, "method": "measure_saved", "sources": sources}},
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "legal_verdict_claimed": False}


def saved_result(attempt: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("saved construction identity differs")
    description = construction["recording_description"]
    measurement = report["measurements"]["cycle_lane_intersection_observation"]["value"]
    rows = json.loads((attempt / "history.json").read_text())
    channels = attempt / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    for entry in description["channels"]:
        name = entry["name"]
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for row in rows:
                value = (row["ego_body_polygon"] if name == "ego_body_polygon" else
                         row["ego_body_in_intersection"] and
                         row["ego_body_in_designated_cycle_lane"])
                stream.write(json.dumps({"time_s": row["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": entry["unit"],
                         "reference": str(path.relative_to(attempt))})
    context = channels / "context.json"
    context.write_text(json.dumps({"reviewed_site_and_subsection_3": {
        "source_kind": measurement["source_kind"],
        "source_sha256": report["measurements"]["cycle_lane_intersection_observation"]["sources"]}}) + "\n")
    for entry in description["context_inputs"]:
        evidence.append({"name": entry["name"], "unit": entry["unit"],
                         "reference": str(context.relative_to(attempt))})
    overlap = measurement["intersection_cycle_lane_overlap_frames"]
    requested = config["requested_overlap"]
    result = {"case_id": case_id, "measured_values": measurement,
              "target_checks": [{"target": "intersection and designated cycle-lane body overlap",
                                 "requested": requested, "measured": overlap > 0,
                                 "method": "900 original/source-shaped polygon joins",
                                 "tolerance": 0, "matched": (overlap > 0) == requested,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": report["measurements"]["cycle_lane_intersection_observation"]["sources"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved cycle-lane assessment awaits physical review",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((args.attempt / "config.json").read_text())
    report = analyze(args.attempt, config["selected_case_id"])
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
