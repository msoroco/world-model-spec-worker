"""Saved-only school-lane measurements and diagnostic compatibility finalizer."""

import argparse
import hashlib
import json
from pathlib import Path

from school_lane_observations import observe


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources(attempt):
    context = attempt / "context.json"
    trace = attempt / "trace.json"
    for path in (context, trace):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    return context, trace


def diagnostic_measure(attempt, case_id):
    context_path, trace_path = sources(attempt)
    context = json.loads(context_path.read_text())
    trace = json.loads(trace_path.read_text())
    if (context.get("case_id"), trace.get("case_id")) != (case_id, case_id):
        raise ValueError("diagnostic source case identity differs")
    if trace.get("diagnostic_fixture") is not True or context.get("diagnostic_fixture") is not True:
        receipt = attempt / "original-receipt.json"
        if not receipt.is_file():
            raise ValueError("Missing required source: original-receipt.json")
        return observe(case_id, context_path, trace_path, receipt)
    rows = trace.get("frames")
    if not isinstance(rows, list) or len(rows) != 900:
        raise ValueError("diagnostic 900-frame trace required")
    nearest = context["school_lane_nearest_side_station_m"]
    samples = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or row.get("time_s") != index / 20:
            raise ValueError("diagnostic frame identity differs")
        samples.append({"frame": index, "time_s": row["time_s"],
                        "ego_speed_mps": row["ego_speed_mps"],
                        "ego_reference_station_m": row["ego_reference_station_m"],
                        "reference_to_nearest_side_distance_ft":
                            (nearest - row["ego_reference_station_m"]) / .3048,
                        "complete_cessation_sample": row["ego_speed_mps"] == 0,
                        **{key: row[key] for key in ("human_warning_active", "person_stationed",
                           "children_about_to_cross_or_crossing", "human_go_signal",
                           "human_left_locality", "device_signal_stopped_raised_or_removed")}})
    return {"assignment_id": context["assignment_id"], "case_id": case_id,
            "school_lane_nearest_side_station_m": nearest,
            "vehicle_reference_point_source_label": context["vehicle_reference_point"],
            "first_zero_speed_frame": next((row["frame"] for row in samples if row["complete_cessation_sample"]), None),
            "samples": samples, "physical_acceptance": "unverified",
            "fifty_foot_legal_measurement_convention": "unresolved",
            "stopped_not_less_than_fifty_feet_judgment": "unresolved",
            "proceed_after_release_judgment": "unresolved"}


def school_lane_stop_observation(measured):
    zero = [row for row in measured["samples"] if row["complete_cessation_sample"]]
    return {"first_zero_speed_frame": measured["first_zero_speed_frame"],
            "first_zero_speed_reference_distance_ft": zero[0]["reference_to_nearest_side_distance_ft"] if zero else None,
            "nearest_side_station_m": measured["school_lane_nearest_side_station_m"],
            "vehicle_reference_point": measured["vehicle_reference_point_source_label"],
            "legal_measurement_convention": "unresolved"}


def school_lane_release_observation(measured):
    rows = measured["samples"]
    return {"first_human_go_frame": next((r["frame"] for r in rows if r["human_go_signal"]), None),
            "first_human_departure_frame": next((r["frame"] for r in rows if r["human_left_locality"]), None),
            "first_device_release_frame": next((r["frame"] for r in rows if r["device_signal_stopped_raised_or_removed"]), None),
            "first_proceed_frame": next((b["frame"] for a, b in zip(rows, rows[1:])
                                        if a["ego_speed_mps"] == 0 and b["ego_speed_mps"] > 0), None),
            "release_condition_legal_judgment": "unresolved"}


def school_lane_warning_observation(measured):
    rows = measured["samples"]
    return {"first_human_warning_frame": next((r["frame"] for r in rows if r["human_warning_active"]), None),
            "first_child_crossing_frame": next((r["frame"] for r in rows if r["children_about_to_cross_or_crossing"]), None),
            "stationed_person_seen": any(r["person_stationed"] for r in rows),
            "child_warning_legal_judgment": "unresolved"}


def build_report(attempt, case_id):
    context, trace = sources(attempt)
    measured = diagnostic_measure(attempt, case_id)
    bindings = {"context.json": sha(context), "trace.json": sha(trace)}
    entries = (("school_lane_stop_observation", school_lane_stop_observation),
               ("school_lane_release_observation", school_lane_release_observation),
               ("school_lane_warning_observation", school_lane_warning_observation))
    measurements = {name: {"value": method(measured), "method": name,
                           "sources": bindings} for name, method in entries}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": measurements, "analysis_complete": True,
            "diagnostic_fixture": json.loads(trace.read_text()).get("diagnostic_fixture") is True,
            "legal_verdict_claimed": False}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, validate_result
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case_id = config["selected_case_id"]
    if report["case_id"] != case_id or construction["case_id"] != case_id:
        raise ValueError("saved exact-case identity differs")
    description = construction["recording_description"]
    context = json.loads((attempt / "context.json").read_text())
    trace = json.loads((attempt / "trace.json").read_text())
    rows = trace["frames"]
    channels = attempt / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for index, row in enumerate(rows):
                if name == "school_lane_nearest_side_geometry":
                    value = context["school_lane_nearest_side_station_m"]
                elif name == "ego_reference_station_and_speed":
                    value = {"station_m": row["ego_reference_station_m"], "speed_mps": row["ego_speed_mps"]}
                elif name == "human_warning_children_and_release":
                    value = {key: row[key] for key in ("human_warning_active", "person_stationed",
                              "children_about_to_cross_or_crossing", "human_go_signal", "human_left_locality")}
                elif name == "device_warning_and_release":
                    value = {"stopped_raised_or_removed": row["device_signal_stopped_raised_or_removed"]}
                elif name == "four_synchronized_camera_views":
                    value = {"frame": index, "views": ["overview", "approach", "reference_corner", "driver_reference"]}
                elif name == "original_warning_onset_s":
                    value = next((r["time_s"] for r in rows if r["human_warning_active"]), -1.0)
                elif name == "original_departure_onset_s":
                    value = next((r["time_s"] for r in rows if r["human_left_locality"]), -1.0)
                else:
                    raise ValueError("unsupported school-lane channel: " + name)
                stream.write(json.dumps({"time_s": index / 20, "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_record = {"municipal jurisdiction and reviewed school-lane authority": {
        "source_kind": "synthetic CPU fixture" if report["diagnostic_fixture"] else "original site pending independent audit",
        "physical_reviewed": False}}
    (channels / "context.json").write_text(json.dumps(context_record) + "\n")
    for channel in description["context_inputs"]:
        evidence.append({"name": channel["name"], "unit": channel["unit"],
                         "reference": "channels/context.json"})
    target = report["measurements"]["school_lane_stop_observation"]["value"]
    requested_distance = config.get("stop_distance_target_ft")
    measured_distance = target["first_zero_speed_reference_distance_ft"]
    requested_target = requested_distance if requested_distance is not None else 1
    measured_target = measured_distance if measured_distance is not None else 1
    tolerance = 1.0 if requested_distance is not None else 0.0
    result = {"case_id": case_id, "measured_values": report["measurements"],
              "target_checks": [{"target": "vehicle full cessation at authored engineering station",
                                 "requested": requested_target,
                                 "measured": measured_target,
                                 "method": "original body-reference and nearest-side samples",
                                 "tolerance": tolerance,
                                 "matched": abs(requested_target - measured_target) <= tolerance,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": {"context.json": sha(attempt / "context.json"),
                                                    "trace.json": sha(attempt / "trace.json")}}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved source assessment pending independent physical review",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {"school_lane_stop": target,
                "school_lane_release": report["measurements"]["school_lane_release_observation"]["value"],
                "school_lane_warning": report["measurements"]["school_lane_warning_observation"]["value"]}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh analysis report required")
    case_id = args.case or json.loads((args.attempt / "config.json").read_text())["selected_case_id"]
    report = build_report(args.attempt, case_id)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
