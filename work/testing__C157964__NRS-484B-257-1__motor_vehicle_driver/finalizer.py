"""Saved-only C157964 officer-control exception analysis.

Observed direction and control come from the separately source-bound camera
review. Native programmed poses remain raw context, never a substitute for it.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("c157964_saved_officer_measurements",
                                               ROOT / "officer_measurements.py")
MEASURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEASURE)
CAMERAS = MEASURE.CAMERAS
ASSIGNMENT = "testing__C157964__NRS-484B-257-1__motor_vehicle_driver"
EXPECTED = {MEASURE.PREFIX + "officer_active_stop_then_go": (True, "go"),
            MEASURE.PREFIX + "officer_active_hold": (True, "stop"),
            MEASURE.INACTIVE: (False, "none"), MEASURE.ABSENT: (False, "none")}


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output, *, physical_assessor=None, result_writer=None):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain previous saved officer finalization; choose a fresh attempt")
    required = ("config.json", "officer_context.json", "officer_history.jsonl",
                "officer_review.json", "video_frames.jsonl", "trace.jsonl",
                "capture/evidence.jsonl", *(name + ".mkv" for name in CAMERAS))
    for name in required:
        if not (attempt / name).is_file() or not (attempt / name).stat().st_size:
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (config.get("assignment_id") != ASSIGNMENT or case_id not in EXPECTED or
            config.get("law_id") != "NRS-484B-257-1" or
            config.get("cell_id") != "C157964" or
            config.get("actor") != "motor_vehicle_driver" or
            not isinstance(config.get("recording_description"), dict)):
        raise ValueError("Exact C157964 saved case configuration required")
    measured = MEASURE.analyze(attempt)
    if measured["case_id"] != case_id:
        raise ValueError("Original officer source belongs to another case")
    frames, trace, events = (_rows(attempt / name) for name in
                            ("video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl"))
    if len(frames) != len(trace) or len(frames) != len(events):
        raise ValueError("Original officer camera, trace and evidence counts differ")
    for frame, motion, event in zip(frames, trace, events):
        if (motion.get("frame") != frame["carla_frame"] or
                motion.get("time_s") != frame["time_s"] or
                event.get("original_frame") != frame["carla_frame"]):
            raise ValueError("Original officer trace or evidence frame join failed")
    sources = {name: _sha(attempt / name) for name in required}
    requested_control, requested_direction = EXPECTED[case_id]
    entry = measured["first_ego_entry"]
    checks = [
        {"target": "officer_control_observed_at_ego_entry",
         "requested": requested_control,
         "measured": entry["traffic_control_observed"],
         "method": "source-reviewed original officer camera frames joined to complete ego body entry",
         "tolerance": 0,
         "matched": entry["traffic_control_observed"] is requested_control,
         "physical_cause_confirmed": False,
         "cause_evidence": ["officer_review.json", "officer_history.jsonl", "video_frames.jsonl"]},
        {"target": "officer_direction_observed_at_ego_entry",
         "requested": requested_direction,
         "measured": entry["officer_direction_observed"],
         "method": "source-reviewed original camera direction at ego body entry",
         "tolerance": "exact categorical observation",
         "matched": entry["officer_direction_observed"] == requested_direction,
         "physical_cause_confirmed": False,
         "cause_evidence": ["officer_review.json", "video_frames.jsonl"]},
    ]
    channels = attempt / "channels"
    channels.mkdir()
    for name, key in (("officer_control_observed", "traffic_control_observed"),
                      ("officer_direction_observed", "direction"),
                      ("ego_speed_mps", "ego_speed_mps"),
                      ("ego_body_in_intersection", "ego_body_in_intersection")):
        with (channels / (name + ".jsonl")).open("x") as stream:
            for row in measured["samples"]:
                stream.write(json.dumps({"original_frame": row["frame"],
                                         "time_s": row["time_s"], "value": row[key]},
                                        allow_nan=False) + "\n")
    (channels / "officer_context.json").write_text(json.dumps({
        "case_id": case_id, "fixed_context": measured["fixed_context"],
        "first_ego_entry": entry,
        "police_authority_judgment": measured["police_authority_judgment"],
        "legal_control_exception_judgment": "unresolved",
        "source_sha256": sources, "legal_conclusion": "unresolved"},
        indent=2, allow_nan=False) + "\n")
    result = {"case_id": case_id,
              "measured_values": {"officer_control_observed_at_ego_entry": entry["traffic_control_observed"],
                                  "officer_direction_observed_at_ego_entry": entry["officer_direction_observed"],
                                  "first_ego_entry": entry,
                                  "police_authority_judgment": measured["police_authority_judgment"],
                                  "legal_control_exception_judgment": "unresolved"},
              "target_checks": checks,
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved original-source assessment; police authority and legal control unresolved",
              "physical_failure_flags": ["Physical source and officer authority need independent review"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": [
                  {"name": name, "unit": unit, "reference": "channels/" + name + ".jsonl"}
                  for name, unit in (("officer_control_observed", "count"),
                                     ("officer_direction_observed", "text"),
                                     ("ego_speed_mps", "m/s"),
                                     ("ego_body_in_intersection", "count"))]
                  + [{"name": "officer_context", "unit": "structured record",
                      "reference": "channels/officer_context.json"}],
              "source_evidence_hashes": sources,
              "realized_observables": {}}
    if physical_assessor is None or result_writer is None:
        from worker_exchange.native_output import physical_result, write_result
        physical_assessor = physical_result
        result_writer = write_result
    result = physical_assessor(attempt, result)
    result_writer(attempt, result)
    analysis = {"format": "worker-c157964-officer-saved-analysis",
                "case_id": case_id,
                "measurements": {"officer_control_at_entry": {
                    "value": entry["traffic_control_observed"],
                    "method": "original_camera_review_joined_to_ego_entry",
                    "sources": {name: sources[name] for name in
                                ("officer_history.jsonl", "officer_review.json",
                                 "video_frames.jsonl")}},
                    "officer_direction_at_entry": {
                    "value": entry["officer_direction_observed"],
                    "method": "original_camera_review_joined_to_ego_entry",
                    "sources": {name: sources[name] for name in
                                ("officer_review.json", "video_frames.jsonl")}}},
                "source_report": measured,
                "physical_checks": result.get("physical_checks", {}),
                "realized_observables": result["realized_observables"],
                "analysis_complete": True,
                "physical_acceptance_claimed": False,
                "legal_conclusion": "unresolved"}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = finalize(args.attempt, args.output)
    print(json.dumps({"case_id": report["case_id"],
                      "analysis_complete": report["analysis_complete"],
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
