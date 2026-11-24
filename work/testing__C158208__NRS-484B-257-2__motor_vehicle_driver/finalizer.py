"""Saved-only signed-entrance measurements from original joined source frames."""

import argparse
import hashlib
import json
from pathlib import Path

from yield_entry_measurements import analyze
from yield_stage import KINDS, PREFIX

CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")

MEASUREMENT_INPUTS = {
    "signed_entrance": ("intersection_context.json", "site_review.json", "video_frames.jsonl", *CAMERAS),
    "entry_reference": ("intersection_context.json", "site_review.json", "video_frames.jsonl", *CAMERAS),
    "initial_yield_response": ("entry_history.jsonl", "video_frames.jsonl", "site_review.json"),
    "other_entrance_obligation": ("intersection_context.json", "entry_history.jsonl", "video_frames.jsonl"),
    "other_crossing_relation": ("entry_history.jsonl", "video_frames.jsonl", "intersection_context.json"),
    "control_exception": ("intersection_context.json", "site_review.json", "video_frames.jsonl", *CAMERAS),
}


def measure_signed_entrance(report):
    return {"non_through_highway": report["non_through_highway"],
            "yield_sign_id": report["native_yield_sign_id"]}


def measure_entry_reference(report):
    return report["subsection_one_reference"]


def measure_initial_yield_response(report):
    return {"first_entry": report["first_ego_entry"],
            "slowed_or_stopped_before_reference": report["observed_slowed_or_stopped_before_reference"]}


def measure_other_entrance_obligation(report):
    return {"device": report["other_entrance_device"],
            "not_obligated_by_stop_or_yield": report["other_not_obligated_by_stop_or_yield"]}


def measure_other_crossing_relation(report):
    return {"inside_at_ego_entry": report["other_inside_at_ego_entry"],
            "samples": [{"frame": row["frame"], "time_s": row["time_s"],
                         "inside": row["other_body_in_intersection"],
                         "closing_mps": row["other_center_closing_mps"]}
                        for row in report["samples"]]}


def measure_control_exception(report):
    return {"officer_control_observed": report["officer_control_observed"],
            "officer_source_sha256": report["officer_control_source_sha256"],
            "authority_judgment": "unresolved", "signal_control": False}


def bound_measurements(report):
    methods = {
        "signed_entrance": measure_signed_entrance,
        "entry_reference": measure_entry_reference,
        "initial_yield_response": measure_initial_yield_response,
        "other_entrance_obligation": measure_other_entrance_obligation,
        "other_crossing_relation": measure_other_crossing_relation,
        "control_exception": measure_control_exception,
    }
    values = {key: {"value": method(report), "method": method.__name__,
                    "sources": {name: report["sources"][name] for name in MEASUREMENT_INPUTS[key]}}
              for key, method in methods.items()}
    if report["officer_control_observed"]:
        name = "officer_review.json"
        values["control_exception"]["sources"][name] = report["sources"][name]
    return values


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _target(case_id, report):
    kind = case_id.removeprefix(PREFIX)
    if kind not in KINDS:
        raise ValueError("Wrong exact signed-entrance case")
    if kind == "yield_other_inside":
        name, requested, measured = "other_body_inside_at_ego_entry", True, report["other_inside_at_ego_entry"]
    elif kind == "yield_other_approaching":
        before = [sample for sample in report["samples"]
                  if sample["time_s"] <= report["first_ego_entry"]["time_s"]]
        name, requested = "other_center_closing_before_ego_entry", True
        measured = any(sample["other_center_closing_mps"] is not None
                       and sample["other_center_closing_mps"] > 0 for sample in before)
    elif kind == "yield_other_obligated":
        name, requested, measured = ("other_stop_or_yield_obligation", True,
                                     not report["other_not_obligated_by_stop_or_yield"])
    elif kind == "yield_no_slow":
        name, requested, measured = ("no_observed_pre_reference_slowing", True,
                                     not report["observed_slowed_or_stopped_before_reference"])
    else:
        name, requested, measured = "originally_reviewed_officer_control", True, report["officer_control_observed"]
    return {"target": name, "requested": requested, "measured": measured,
            "method": "original_source_joined_saved_measurement",
            "tolerance": 0, "matched": requested == measured,
            "physical_cause_confirmed": False,
            "cause_evidence": ["entry_history.jsonl", "video_frames.jsonl",
                               "intersection_context.json", "site_review.json"]}


def build_result(attempt, config, report):
    attempt = Path(attempt)
    case_id = config.get("selected_case_id")
    target = _target(case_id, report)
    samples = report["samples"]
    channels = {
        "ego_speed_mps": [row["ego_speed_mps"] for row in samples],
        "ego_body_in_intersection": [int(row["ego_body_in_intersection"]) for row in samples],
        "other_body_in_intersection": [int(row["other_body_in_intersection"]) for row in samples],
        "other_distance_to_intersection_center_m": [row["other_distance_to_intersection_center_m"] for row in samples],
        "other_center_closing_mps": [row["other_center_closing_mps"] if row["other_center_closing_mps"] is not None else 0.0 for row in samples],
        "other_center_closing_valid": [int(row["other_center_closing_mps"] is not None) for row in samples],
        "ego_before_yield_reference": [int(row["ego_body_before_yield_reference"]) for row in samples],
    }
    units = {"ego_speed_mps": "m/s", "ego_body_in_intersection": "count",
             "other_body_in_intersection": "count",
             "other_distance_to_intersection_center_m": "m",
             "other_center_closing_mps": "m/s", "other_center_closing_valid": "count",
             "ego_before_yield_reference": "count"}
    evidence = [{"name": name, "unit": units[name],
                 "reference": "channels/" + name + ".jsonl"} for name in channels]
    for name in ("signed_intersection_status_and_all_entrances", "site_and_officer_review"):
        evidence.append({"name": name, "unit": "structured record",
                         "reference": "channels/" + name + ".json"})
    result = {"case_id": case_id,
              "measured_values": {"first_ego_entry": report["first_ego_entry"],
                                  "observed_slowed_or_stopped_before_reference": report["observed_slowed_or_stopped_before_reference"],
                                  "other_inside_at_ego_entry": report["other_inside_at_ego_entry"],
                                  "other_not_obligated_by_stop_or_yield": report["other_not_obligated_by_stop_or_yield"],
                                  "officer_control_observed": report["officer_control_observed"]},
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved source analysis; independent physical audit pending",
              "physical_failure_flags": ["Native and original-pixel physical review pending"],
              "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": evidence,
              "source_evidence_hashes": report["sources"],
              "capture_evidence_sha256": _sha(attempt / "capture/evidence.jsonl"),
              "realized_observables": {}}
    return result, channels


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain previous saved finalization; use a fresh attempt")
    for name in ("config.json", "trace.jsonl", "capture/evidence.jsonl",
                 "intersection_context.json", "entry_history.jsonl",
                 "video_frames.jsonl", "site_review.json", *CAMERAS):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    report = analyze(attempt)
    result, values = build_result(attempt, config, report)
    channels = attempt / "channels"
    channels.mkdir()
    for name, series in values.items():
        with (channels / (name + ".jsonl")).open("x") as stream:
            for row, value in zip(report["samples"], series):
                stream.write(json.dumps({"original_frame": row["frame"],
                                         "time_s": row["time_s"], "value": value},
                                        allow_nan=False) + "\n")
    status = {"signed_intersection_status_and_all_entrances": {
        "non_through_highway": report["non_through_highway"],
        "native_yield_sign_id": report["native_yield_sign_id"],
        "other_entrance_device": report["other_entrance_device"],
        "other_not_obligated_by_stop_or_yield": report["other_not_obligated_by_stop_or_yield"],
        "source_sha256": report["sources"]["intersection_context.json"]}}
    review = {"site_and_officer_review": {"subsection_one_reference": report["subsection_one_reference"],
        "officer_control_observed": report["officer_control_observed"],
        "officer_source_sha256": report["officer_control_source_sha256"],
        "closing_rate_first_frame_valid": False,
        "immediate_hazard_judgment": "unresolved", "caution_and_yield_judgment": "unresolved",
        "proper_sign_judgment": "unresolved", "legal_conclusion": "unresolved"}}
    for name, context in (("signed_intersection_status_and_all_entrances", status),
                          ("site_and_officer_review", review)):
        (channels / (name + ".json")).write_text(json.dumps(context, indent=2) + "\n")
    from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    write_result(attempt, result)
    output.write_text(json.dumps({"format": "worker-c158208-signed-entrance-analysis",
                                  "case_id": config["selected_case_id"],
                                  "measurements": bound_measurements(report),
                                  "raw_observations": report,
                                  "physical_checks": result["physical_checks"],
                                  "legal_conclusion": "unresolved",
                                  "analysis_complete": True},
                                 indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == "__main__":
    main()
