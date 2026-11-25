"""Saved-only measurement for exact mounted-rider encounters; no legal verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_encounter import CAMERAS, finalize_saved


def _write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def measure_rider_encounter(measurement):
    """Return the observed mounted rider, driver response, gap and contact."""
    return {"rider_kind": measurement["rider_kind"],
            "response": measurement["response"],
            "minimum_surface_gap_m": measurement["min_surface_gap_m"],
            "contact_observed": measurement["contact_observed"],
            "frames": measurement["frames"]}


def finalize(attempt, report_path):
    root = Path(attempt).resolve()
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    source_names = ("site.json", "history.json", "camera-frames.json")
    for name in source_names:
        if not (root / name).is_file():
            raise ValueError("Missing required source: " + name)
    saved = finalize_saved(root)
    if saved["case_id"] != config["selected_case_id"]:
        raise ValueError("selected case and original encounter differ")
    rows = json.loads((root / "history.json").read_text(encoding="utf-8"))
    packet = json.loads((root / "encounter-packet.json").read_text(encoding="utf-8"))
    expected_frames = 9 if packet.get("diagnostic_fixture") is True else 900
    if len(rows) != expected_frames or not (root / "video_frames.jsonl").is_file():
        raise ValueError("original encounter acquisition incomplete")
    measurement = saved["measurement"]
    channel_values = {
        "rider_classification": lambda row: {"kind": row["rider_kind_observed"],
                                                "person_actor_id": row["rider_person_actor_id"],
                                                "mounted": row["rider_mounted_observed"]},
        "driver_response": lambda row: row["ego_brake_observed"],
        "separation": lambda row: row["surface_gap_m"],
        "contact": lambda row: row["contact_observed"],
        "camera_frame_map": lambda row: {"frame": row["frame"], "views": list(CAMERAS)},
    }
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        if name not in channel_values:
            raise ValueError("unknown source channel: " + name)
        path = root / ("observed-" + name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "value": channel_values[name](row)}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": path.name})
    context = root / "observed-site-context.json"
    _write(context, {"reviewed_original_site": saved["map_sha256"]})
    evidence.append({"name": "reviewed_original_site", "unit": "structured record",
                     "reference": context.name})
    video_references = [camera + ".mkv" for camera in CAMERAS]
    if any(not (root / name).is_file() for name in video_references):
        raise ValueError("four composed source videos required")
    kind = config["case"]["rider_kind"]
    response = config["case"]["motorist_response"]
    checks = [
        {"target": "rider_kind", "requested": kind, "measured": measurement["rider_kind"],
         "method": "sealed original rider asset and frame history", "tolerance": "exact",
         "matched": measurement["rider_kind"] == kind, "physical_cause_confirmed": False,
         "cause_evidence": "original mounted actor history; independent visual review pending"},
        {"target": "motorist_response", "requested": response, "measured": measurement["response"],
         "method": "original 20 Hz brake control readback in conflict window", "tolerance": "exact",
         "matched": measurement["response"] == response, "physical_cause_confirmed": False,
         "cause_evidence": "response observed but physical causal and legal review pending"},
    ]
    result = {
        "case_id": saved["case_id"], "measured_values": measurement,
        "target_checks": checks,
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "900 saved original encounter frames analyzed; physical and legal review pending",
        "physical_failure_flags": ["physical_completion_unreviewed", "camera_visibility_unreviewed"],
        "trace_reference": "trace.jsonl", "video_references": video_references,
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["case"]["recording_description"],
        "recording_evidence": evidence,
        "realized_observables": {
            "min_surface_gap_m": {"value": measurement["min_surface_gap_m"],
                "unit": "m", "statistic": "min", "method": "original encounter gap samples",
                "time_window": "observed conflict window", "reference": "observed-separation.jsonl"}},
        "source_review": saved,
        "legal_judgment_status": "unresolved_review",
    }
    _write(root / "result.json", result)
    source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                     for name in source_names}
    report = {"format": "c111260-saved-measurement-v1", "case_id": saved["case_id"],
              "measurement": measurement, "source_hashes": saved["source_hashes"],
              "measurements": {"mounted_rider_encounter": {
                  "method": "measure_rider_encounter",
                  "value": measure_rider_encounter(measurement),
                  "sources": source_hashes}},
              "original_frames": saved["original_frames"],
              "legal_judgment": "unresolved_review", "physical_completion": False}
    _write(report_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    finalize(args.attempt, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
