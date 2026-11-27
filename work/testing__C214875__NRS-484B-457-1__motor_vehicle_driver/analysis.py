"""Saved-only measurements from sealed original curb, wheel and activity sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_original_attempt import audit


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _required(path, relative):
    target = Path(path) / relative
    if target.is_symlink() or not target.is_file():
        raise ValueError("Missing required source: " + relative)
    return target


def measure_curb_activity(measured, site):
    return {"public_highway_reviewed": site["reviewed_assertions"]["public_highway"],
            "adjacent_right_curb_reviewed": site["reviewed_assertions"]["adjacent_right_curb"],
            "residence_district_reviewed": site["reviewed_assertions"]["residence_district"],
            "stopped_frame_count": len(measured["stopped_frames"]),
            "parking_brake_frame_count": len(measured["parking_brake_frames"]),
            "stopped_without_parking_brake_frame_count": len(measured["stopped_without_parking_brake_frames"])}


def measure_curb_geometry(measured, site):
    return {"max_right_wheel_distance_inches": measured["max_right_wheel_distance_inches"],
            "max_wheel_curb_alignment_deg": measured["max_wheel_curb_alignment_deg"],
            "right_curb_source_sha256": site["sources"]["curb_survey"]["sha256"],
            "statutory_distance_inches": 18,
            "legal_parallel_judgment": "unresolved"}


def source_section_exceptions(measured, site):
    return {"left_curb_ordinance_applies": site["reviewed_assertions"]["left_curb_ordinance_applies"],
            "angle_parking_ordinance_applies": site["reviewed_assertions"]["angle_parking_ordinance_applies"],
            "ordinance_source_sha256": site["sources"]["local_ordinance"]["sha256"],
            "dot_status_source_sha256": site["sources"]["dot_status"]["sha256"],
            "legal_interpretation": "unresolved"}


INPUTS = {
    0: ("original-attempt/site.json", "original-attempt/plan.json",
        "original-attempt/wheel-motion.jsonl", "original-attempt/wheel-seal.json",
        "original-attempt/frame-map.json"),
    1: ("original-attempt/site.json", "original-attempt/curb_survey.source",
        "original-attempt/wheel-motion.jsonl", "original-attempt/wheel-seal.json"),
    2: ("original-attempt/site.json", "original-attempt/local_ordinance.source",
        "original-attempt/dot_status.source"),
}


def build(attempt):
    attempt = Path(attempt)
    config = json.loads(_required(attempt, "config.json").read_text())
    case_id = config["selected_case_id"]
    for paths in INPUTS.values():
        for relative in paths:
            _required(attempt, relative)
    checked = audit(attempt, case_id)
    site = json.loads(_required(attempt, "original-attempt/site.json").read_text())
    measured = checked["measurement"]
    functions = (measure_curb_activity, measure_curb_geometry, source_section_exceptions)
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "analysis_complete": True, "legal_verdict_claimed": False,
              "source_audit": checked, "measurements": {},
              "limitations": ["Original pixel visibility, physical completion and legal parallel judgment require local review."]}
    for index, function in enumerate(functions):
        paths = INPUTS[index]
        report["measurements"]["curb_requirement_" + str(index)] = {
            "method": function.__name__, "value": function(measured, site),
            "sources": {relative: _sha(attempt / relative) for relative in paths}}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to replace saved curb analysis")
    report = build(args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
