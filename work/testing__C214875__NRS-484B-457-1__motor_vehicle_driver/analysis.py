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


def saved_result(attempt, report):
    """Build canonical evidence from the sealed original source after Native exit."""
    from worker_exchange.native_output import validate_result

    root = Path(attempt)
    config = json.loads(_required(root, "config.json").read_text())
    construction = json.loads(_required(root, "construction.json").read_text())
    description = construction["recording_description"]
    original = root / "original-attempt"
    rows = [json.loads(line) for line in _required(root, "original-attempt/wheel-motion.jsonl").read_text().splitlines()]
    mapping = json.loads(_required(root, "original-attempt/frame-map.json").read_text())["frames"]
    if len(rows) != len(mapping) or not rows:
        raise ValueError("original right-curb rows and frame map differ")
    site = json.loads(_required(root, "original-attempt/site.json").read_text())
    checked = report["source_audit"]
    measured = checked["measurement"]
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as output:
            for row, frame in zip(rows, mapping):
                if row["native_frame"] != frame["native_frame"] or row["time_s"] != frame["native_time_s"]:
                    raise ValueError("original right-curb channel frame identity differs")
                if name == "public_highway_and_adjacent_curb":
                    value = {k: site["reviewed_assertions"][k] for k in ("public_highway", "adjacent_right_curb")}
                elif name == "right_hand_wheel_positions":
                    value = {k: row[k] for k in ("right_front_wheel_xy_m", "right_rear_wheel_xy_m")}
                elif name == "parallel_curb_alignment":
                    value = measured["max_wheel_curb_alignment_deg"]
                elif name == "stopped_or_parked_activity":
                    value = {k: row[k] for k in ("speed_mps", "parking_brake_applied")}
                elif name == "local_ordinance_and_department_context":
                    value = {k: site["reviewed_assertions"][k] for k in
                             ("left_curb_ordinance_applies", "angle_parking_ordinance_applies")}
                elif name == "four_camera_original_pixels":
                    value = {"original_frame": row["native_frame"], "views": ["overview", "approach",
                             "reference_corner", "driver_reference"], "pixel_review_pending": True}
                else:
                    raise ValueError("unsupported right-curb channel: " + name)
                output.write(json.dumps({"time_s": row["time_s"], "value": value}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": str(path.relative_to(root))})
    context = channels / "context.json"
    context.write_text(json.dumps({"reviewed_right_curb_site": site}, sort_keys=True) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(root))})
    requested = float(config["case"]["case_id"].rsplit("__", 1)[1].split("in", 1)[0].split("_")[-1])
    actual = measured["max_right_wheel_distance_inches"]
    matched = abs(actual - requested) <= .1
    complete = (len(rows) == config["frame_count"] and
                len(measured["stopped_frames"]) == len(rows) and
                len(measured["parking_brake_frames"] if config["variant"].startswith("park") else
                    measured["stopped_without_parking_brake_frames"]) == len(rows))
    sources = measured["source_hashes"]
    check = {"status": "met" if complete else "not_met",
             "method": "source-sealed original wheel, activity and camera-frame join",
             "sources": sources, "diagnostic_fixture": checked["diagnostic_fixture"],
             "legal_verdict_claimed": False}
    result = {"case_id": config["selected_case_id"], "measured_values": measured,
              "target_checks": [{"target": "requested right-wheel curb distance in inches",
                                 "requested": requested, "measured": actual,
                                 "method": "source-sealed original right-wheel measurement",
                                 "tolerance": .1, "matched": matched,
                                 "physical_cause_confirmed": False, "cause_evidence": sources}],
              "setup_confirmed": complete, "behavior_attempted": complete,
              "maneuver_completed": complete, "physical_checks": {"maneuver": check},
              "termination_reason": "saved original curb/activity assessment; physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}, "diagnostic_fixture": checked["diagnostic_fixture"],
              "provenance_kind": "synthetic_fixture" if checked["diagnostic_fixture"] else "native_capture"}
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to replace saved curb analysis")
    report = build(args.attempt)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
