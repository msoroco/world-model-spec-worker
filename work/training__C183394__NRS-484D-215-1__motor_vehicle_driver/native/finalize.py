"""Recorded-only Native beam measurement and nonlegal report."""
import argparse
import json
from pathlib import Path

from saved_beam import CAMERAS, SOURCES, load_rows, measure_saved, source
from worker_exchange.native_output import physical_result, write_result


CHANNELS = ("sig.headlamp", "rel.oncoming", "rel.centre_distance",
            "drv.approaching", "drv.civil_night", "env.civil_time",
            "st.roadway", "st.shoulder", "env.visibility")


def activation_beam_context(measured, root):
    """Return observed position and the requested, still unverified lighting trigger."""
    road = json.loads(source(root, "road-position-source.json").read_text())
    trigger = json.loads(source(root, "lighting-trigger-source.json").read_text())
    return {"road_position": road["road_position"],
            "lighting_trigger": trigger["lighting_trigger"],
            "civil_time_condition_verified": trigger.get("civil_time_condition_verified", False),
            "sufficient_illumination_review_required": True}


def oncoming_beam_interaction(measured, root):
    """Return original measured approach/lamp counts without a glare conclusion."""
    return {"minimum_centre_distance_m": measured["minimum_centre_distance_m"],
            "within_500_feet_frames": measured["within_500_feet_frames"],
            "preentry_low_beam_request_frames": measured["preentry_low_beam_request_frames"],
            "low_beam_request_within_500_feet_frames": measured["low_beam_request_within_500_feet_frames"],
            "high_beam_request_within_500_feet_frames": measured["high_beam_request_within_500_feet_frames"],
            "glare_at_eyes_conclusion": None}


def finalize(attempt, output):
    root, destination = Path(attempt).resolve(), Path(output)
    if destination.exists():
        raise ValueError("Retain prior selected beam measurement")
    measured = measure_saved(root)
    config = json.loads(source(root, "config.json").read_text())
    rows = load_rows(source(root, "beam-rows.jsonl"))
    frames = load_rows(source(root, "video_frames.jsonl"))
    trace = load_rows(source(root, "trace.jsonl"))
    if len(trace) != 600 or any(pose.get("frame") != frame["native_frame"]
                                   for pose, frame in zip(trace, frames)):
        raise ValueError("original beam trace/frame identity differs")
    channels = root / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    for name in CHANNELS:
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for row in rows:
                value = {"native_frame": row["native_frame"],
                         "requested_beam_state": row["requested_beam_state"],
                         "observed_light_state_bits": row.get("observed_light_state_bits"),
                         "oncoming_x_m": row["oncoming_x_m"],
                         "oncoming_y_m": row["oncoming_y_m"],
                         "civil_time_condition_verified": False,
                         "driver_eye_glare_judgment": "independent_original_review_required"}
                stream.write(json.dumps({"time_s": row["time_s"], "value": value},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": "structured",
                         "reference": "channels/" + path.name})
    provenance = json.loads(source(root, "acquisition-provenance.json").read_text())
    diagnostic = provenance.get("provenance_kind") == "synthetic_fixture"
    if provenance.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("beam source provenance differs")
    values = measured["measurement"]
    result = {"case_id": config["selected_case_id"],
        "measured_values": values,
        "target_checks": [{"target": "beam request and oncoming vehicle inside 500 feet",
            "requested": config["beam_mode"],
            "measured": values["within_500_feet_frames"],
            "method": "source-bound original actor positions and lamp readback",
            "tolerance": "none for 500-foot quantity; aim/glare and safe distance are judgments",
            "matched": False, "physical_cause_confirmed": False,
            "cause_evidence": list(SOURCES)}],
        "setup_confirmed": False, "behavior_attempted": not diagnostic,
        "maneuver_completed": False,
        "termination_reason": "saved beam sources measured; original optical review pending",
        "physical_failure_flags": ["Original beam aim, eye exposure and civil time review pending"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": evidence,
        "realized_observables": {},
        "provenance_kind": provenance["provenance_kind"],
        "diagnostic_fixture": diagnostic,
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    report = {"format": "worker-oncoming-beam-measurement",
        "case_id": config["selected_case_id"],
        "measurements": {
            "activation_beam_context": {"method": "activation_beam_context",
                "value": activation_beam_context(values, root),
                "sources": {name: measured["source_sha256"][name] for name in
                            ("road-position-source.json", "lighting-trigger-source.json")}},
            "oncoming_beam_interaction": {"method": "oncoming_beam_interaction",
                "value": oncoming_beam_interaction(values, root),
                "sources": {name: measured["source_sha256"][name] for name in
                            ("beam-rows.jsonl", "oncoming-driver-source.json",
                             "eye-region-source.json", "video_frames.jsonl")}}},
        "legal_compliance": "unassessed", "physical_acceptance_claimed": False}
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
