"""Recorded-only 287(1)(c) analysis and Native result, with no legal verdict."""

import argparse
import hashlib
import json
from pathlib import Path

from original_saved import measure, required, rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def between_intersections_crossing_measurement(attempt):
    value = measure(attempt)
    return {"roadway_entry": value["entry"],
            "observed_frames": value["original_frames"],
            "adjacency_source": "native-survey.json",
            "official_controls_source": "controls-original.jsonl",
            "marking_source": "native-survey-media/marking.txt",
            "physical_acceptance_claimed": False,
            "legal_verdict": None}


def scope_crossing_measurement(attempt):
    value = measure(attempt)
    return {"observed_crossing_location":
            "marked_crosswalk" if value["entry"]["within_marked_crosswalk_polygon"]
            else "unmarked_midblock",
            "entry_native_frame": value["entry"]["native_frame"],
            "both_controls_operating": value["entry"]["both_controls_operating"],
            "legal_verdict": None}


def exception_applicability_measurement(attempt):
    """Preserve the unavailable statute and person-specific facts as unresolved."""
    source = json.loads(required(attempt, "exception-applicability-source.json").read_text())
    if (source.get("format") != "c109166-287-1c-exception-context-v1"
            or source.get("statute") != "NRS 484B.290"
            or source.get("applicability") != "undetermined"
            or source.get("review_status") != "pending_independent_review"):
        raise ValueError("Unreviewed NRS 484B.290 exception may not be resolved by worker")
    return {"statute": "NRS 484B.290", "applicability": "undetermined",
            "review_status": "pending_independent_review", "legal_verdict": None}


def report(attempt, case_id):
    attempt = Path(attempt)
    measured = measure(attempt)
    core_sources = {name: sha(required(attempt, name)) for name in
                    ("pedestrian-original.jsonl", "controls-original.jsonl",
                     "native-survey.json", "video_frames.jsonl")}
    return {"format": "worker-analysis-report-v1", "case_id": case_id,
            "measurements": {
                "between_intersections_crossing": {
                    "method": "between_intersections_crossing_measurement",
                    "value": {"roadway_entry": measured["entry"],
                              "observed_frames": measured["original_frames"],
                              "legal_verdict": None}, "sources": core_sources},
                "crossing_scope": {
                    "method": "scope_crossing_measurement",
                    "value": {"crossing_location": "marked_crosswalk" if
                              measured["entry"]["within_marked_crosswalk_polygon"]
                              else "unmarked_midblock",
                              "entry_native_frame": measured["entry"]["native_frame"],
                              "both_controls_operating": measured["entry"]["both_controls_operating"]},
                    "sources": core_sources},
                "nrs_484b_290_exception": {
                    "method": "exception_applicability_measurement",
                    "value": exception_applicability_measurement(attempt),
                    "sources": {"exception-applicability-source.json":
                                sha(required(attempt, "exception-applicability-source.json"))}}},
            "original_source_sha256": measured["source_sha256"],
            "legal_verdict_claimed": False}


def _channels(attempt, config):
    attempt = Path(attempt)
    mapping = rows(attempt, "video_frames.jsonl")
    people = rows(attempt, "pedestrian-original.jsonl")
    controls = rows(attempt, "controls-original.jsonl")
    survey = json.loads(required(attempt, "native-survey.json").read_text())
    channels = {item["name"]: [] for item in config["recording_description"]["channels"]}
    for frame, person, device in zip(mapping, people, controls):
        values = {
            "ru.subject": person["walker_actor_id"],
            "ru.pedestrian": {"native_actor_id": person["walker_actor_id"]},
            "st.intersection": {"surveyed_junction_ids": survey["junction_ids"]},
            "st.lane_enters": {"source_ref": "native-survey.json",
                                "independent_topology_review": True},
            "dev.traffic_signal": {"controls": device["controls"]},
            "st.crosswalk": {"marked_polygon_xy_m": survey["marked_crosswalk"]["polygon_xy_m"],
                             "original_marking_reviewed": True},
            "rel.occupies": {"walker_footprint_xy_m": person["footprint_xy_m"]},
            "st.roadway": {"entry_y_m": survey["roadway_boundary"]["entry_y_m"]},
            "kin.position": person["center_xy_m"],
        }
        if set(values) != set(channels):
            raise ValueError("Declared observation channels differ from original sources")
        for name, value in values.items():
            channels[name].append({"time_s": frame["time_s"], "value": value})
    directory = attempt / "channels"
    directory.mkdir(exist_ok=False)
    for name, values in channels.items():
        (directory / (name + ".jsonl")).write_text(
            "".join(json.dumps(value, allow_nan=False) + "\n" for value in values))


def finalize(attempt, output):
    from worker_exchange.native_output import validate_result, provenance_record
    from worker_exchange.native_output import assess_physical

    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh saved-analysis stage")
    config = json.loads(required(attempt, "config.json").read_text())
    analysis = report(attempt, config["case_id"])
    _channels(attempt, config)
    measured = analysis["measurements"]["between_intersections_crossing"]["value"]
    observed = measured["roadway_entry"]
    physical = assess_physical(attempt, config)
    requested = config["requested_crossing_location"]
    actual = "marked_crosswalk" if observed["within_marked_crosswalk_polygon"] else "unmarked_midblock"
    evidence = [{"name": name, "unit": "source", "reference": name}
                for name in ("pedestrian-original.jsonl", "controls-original.jsonl",
                             "camera-sources.jsonl", "native-survey.json",
                             "exception-applicability-source.json")]
    evidence += [{"name": item["name"], "unit": item["unit"],
                  "reference": item["source"]}
                 for item in config["recording_description"]["channels"]]
    result = {"case_id": config["case_id"],
              "measured_values": {"roadway_entry_native_frame": observed["native_frame"],
                                  "crossing_location": actual,
                                  "both_controls_operating_at_entry": observed["both_controls_operating"]},
              "target_checks": [{"target": "original crossing location between adjacent controlled intersections",
                                 "requested": requested, "measured": actual,
                                 "method": "original footprint, survey, control and FrameMap join",
                                 "tolerance": 0, "matched": requested == actual,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": ["native-survey.json", "pedestrian-original.jsonl",
                                                    "controls-original.jsonl"]}],
              "setup_confirmed": physical["setup_confirmed"],
              "behavior_attempted": physical["behavior_attempted"],
              "maneuver_completed": physical["maneuver_completed"],
              "physical_checks": physical["physical_checks"],
              "termination_reason": "saved original 600-frame crossing and physical criterion assessed",
              "physical_failure_flags": [] if physical["maneuver_completed"] else
                  ["source-backed complete crossing not established"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name, _, _ in __import__("original_capture").CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": evidence,
              "realized_observables": physical["realized_observables"],
              **provenance_record(attempt),
              "accepted": False, "legal_verdict_claimed": False}
    validate_result(result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    analysis = finalize(args.attempt, args.output)
    print(json.dumps({"case_id": analysis["case_id"], "legal_verdict_claimed": False}))


if __name__ == "__main__":
    main()
