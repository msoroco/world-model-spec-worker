"""Saved-only C272412 source reducer and nonaccepting operator handoff."""

import argparse
import json
from pathlib import Path

from measure import CAMERAS, measure as saved_measure, rows

CHANNELS = ("ego_body", "scooter_body", "body_surface_gap", "left_pass",
            "right_return", "center_marking")


def measure(attempt):
    return saved_measure(attempt)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain original attempt; use a fresh saved result")
    facts = measure(attempt)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case = config.get("case_id")
    if not case or case != construction.get("case_id") or case != config.get("selected_case_id"):
        raise ValueError("Saved selected case identity differs")
    recorded = construction["recording_description"]
    names = [channel.get("name") for channel in recorded.get("channels", [])]
    if names != list(CHANNELS):
        raise ValueError("Saved recording channels differ")
    poses = rows(attempt / "participant-poses.jsonl")
    evidence = []
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    for channel in recorded["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for index, pose in enumerate(poses):
                if name == "ego_body":
                    value = pose["ego"]["body_xy_m"]
                elif name == "scooter_body":
                    value = pose["scooter"]["body_xy_m"]
                elif name == "body_surface_gap":
                    from measure import surface_gap
                    value = surface_gap(pose["ego"], pose["scooter"])
                elif name == "left_pass":
                    value = (facts["first_abreast_frame"] <= index <= facts["last_abreast_frame"]
                             and pose["ego"]["center_xy_m"][1] > pose["scooter"]["center_xy_m"][1])
                elif name == "right_return":
                    value = index == facts["right_return_start_frame"]
                else:
                    value = pose["authored_center_marking"]
                stream.write(json.dumps({"time_s": pose["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": "channels/" + path.name})
    source_review = channels / "source_review.json"
    source_review.write_text(json.dumps({
        "sampling_interval_s": facts["sample_interval_s"],
        "continuous_between_frame_clearance_confirmed": False,
        "safely_clear_legally_judged": False,
        "due_care_legally_judged": False,
        "center_crossing_safety_judged": False,
        "cited_laws_213_217_reviewed": False,
        "original_sources": facts["source_sha256"]}) + "\n")
    evidence.append({"name": "source_review", "unit": "source context",
                     "reference": "channels/source_review.json"})
    from worker_exchange.native_output import write_result
    write_result(attempt, {
        "case_id": case, "measured_values": facts,
        "target_checks": [{"target": "sampled body-to-body minimum and return ordering",
                           "requested": True,
                           "measured": {"minimum_gap_m": facts["minimum_body_surface_gap_m"],
                                        "return_after_abreast": facts["right_return_start_frame"] > facts["last_abreast_frame"]},
                           "method": "source-joined original Native actor body polygons",
                           "tolerance": "50 ms samples; between-frame behavior and safety unreviewed",
                           "matched": False, "physical_cause_confirmed": False,
                           "cause_evidence": facts["source_sha256"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "accepted": False,
        "termination_reason": "Saved measurements; continuous clearance and legal safety review pending",
        "physical_failure_flags": ["Original between-frame clearance and legal safety unreviewed"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in (*sorted(CAMERAS), "raw")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": recorded, "recording_evidence": evidence,
        "realized_observables": {}})
    report = {"format": "worker-analysis-report", "case_id": case,
              "measurements": {"scooter_pass": {"method": "measure", "value": facts,
                                                 "sources": facts["source_sha256"]}},
              "source_complete": True, "physical_or_legal_acceptance": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
