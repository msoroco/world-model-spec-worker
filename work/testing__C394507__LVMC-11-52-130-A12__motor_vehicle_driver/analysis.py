"""Saved-only crosswalk geometry and context finalizer; no legal verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crosswalk_measure import measure, require_file

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def build_report(root):
    root = Path(root)
    config = json.loads(require_file(root, "config.json").read_text())
    case_id = config["selected_case_id"]
    fixture = root / "fixture-provenance.json"
    diagnostic = fixture.is_file()
    if diagnostic:
        provenance = json.loads(fixture.read_text())
        if (provenance.get("diagnostic_fixture") is not True or
                provenance.get("physical_acceptance_claimed") is not False):
            raise ValueError("untrusted diagnostic fixture provenance")
    measured = measure(root, case_id, diagnostic=diagnostic)
    source = measured["source_hashes"]
    video_map = _rows(require_file(root, "video_frames.jsonl"))
    history = json.loads(require_file(root, "original-crosswalk-history.json").read_text())
    if len(video_map) != len(history["samples"]) or any(
            row.get("carla_frame") != sample["frame"] or
            row.get("native_frame") != sample["frame"] or
            abs(row.get("time_s", -100) - sample["time_s"]) > .005
            for row, sample in zip(video_map, history["samples"])):
        raise ValueError("original crossing source/video frame join changed")
    site = json.loads(require_file(root, "original-site.json").read_text())
    return {"format": "worker-analysis-report", "case_id": case_id,
            "diagnostic_fixture": diagnostic, "legal_verdict_claimed": False,
            "analysis_complete": True, "source_decode_passed": True,
            "measurements": {
                "crosswalk_geometry_measurement": {
                    "method": "build_report", "value": {
                        "minimum_body_clearance_m": measured["body_clearance_min_m"],
                        "minimum_frame": measured["minimum_clearance_frame"],
                        "twenty_feet_m_arithmetic_reference": 6.096,
                        "legal_measurement_convention": "unresolved",
                        "crosswalk_marked": measured["crosswalk_marked"]},
                    "sources": source},
                "activity_context_measurement": {
                    "method": "build_report", "value": {
                        "requested_activity": measured["requested_activity"],
                        "stationary_sample_frames": measured["stationary_sample_frames"],
                        "classification": "unresolved"},
                    "sources": source},
                "exception_context_measurement": {
                    "method": "build_report", "value": {
                        "requested_exception": measured["requested_exception"],
                        "exception_judgment": "unresolved",
                        "source_context": {name: site.get(name + "_source_sha256")
                                           for name in ("traffic_conflict", "law_compliance",
                                                        "police_direction", "traffic_device_direction")}},
                    "sources": source}},
            "source_hashes": source,
            "limitations": [
                "Twenty feet is an arithmetic reference; legal distance convention and exact boundary remain unresolved.",
                "Stop, stand, park and exception judgments require independent original context review.",
                "Diagnostic media do not establish original motion, visibility or legal acceptance."]}


def analyze(root, output):
    root = Path(root)
    report = build_report(root)
    construction = json.loads(require_file(root, "construction.json").read_text())
    description = construction["recording_description"]
    measured = measure(root, report["case_id"], diagnostic=report["diagnostic_fixture"])
    samples = json.loads(require_file(root, "original-crosswalk-history.json").read_text())["samples"]
    channel_values = {
        "original_body_polygon": [sample["ego_body_polygon_xy_m"] for sample in samples],
        "original_speed": [sample["ego_speed_mps"] for sample in samples],
        "activity_readback": [sample["activity_readback"] for sample in samples],
        "exception_readback": [sample["exception_readback"] for sample in samples],
        "four_camera_frames": [sample["camera_frames"] for sample in samples],
    }
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in channel_values:
            raise ValueError("unsupported original crosswalk channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for sample, value in zip(samples, channel_values[name]):
                stream.write(json.dumps({"time_s": sample["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root))})
    context = channels / "crosswalk_context.json"
    context.write_text(json.dumps({"jurisdiction_and_crossing_context": {
        "site_sha256": measured["source_hashes"]["original-site.json"],
        "legal_judgment": "unresolved"}}) + "\n")
    for item in description.get("context_inputs", []):
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(root))})
    target = {"target": "source-measured body clearance at planned crossing",
              "requested": measured["requested_clearance_m"],
              "measured": measured["body_clearance_min_m"],
              "method": "crosswalk_measure.measure", "tolerance": 0.25,
              "matched": abs(measured["body_clearance_min_m"] -
                             measured["requested_clearance_m"]) <= .25,
              "physical_cause_confirmed": False,
              "cause_evidence": measured["source_hashes"]}
    result = {"case_id": report["case_id"], "measured_values": measured,
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Original source and physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}, "legal_judgment": None,
              "physical_acceptance_claimed": False}
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(root, result)
    if report["diagnostic_fixture"]:
        for check in result["physical_checks"].values():
            check["status"] = "unverified"
            check["missing_evidence"] = ["original Native physical capture and review"]
        result["setup_confirmed"] = False
        result["behavior_attempted"] = False
        result["maneuver_completed"] = False
    validate_result(result)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    with (root / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    with Path(output).open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == "__main__":
    main()
