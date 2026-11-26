"""Saved-only C380107 measurements; diagnostic fixtures never imply legal success."""

import argparse
import hashlib
import json
from pathlib import Path

from hov_encounter_observations import observe


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources(attempt):
    context, trace = attempt / "context.json", attempt / "trace.json"
    for path in (context, trace):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    return context, trace


def measured_source(attempt, case_id):
    context_path, trace_path = sources(attempt)
    context = json.loads(context_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if context.get("case_id") != case_id or trace.get("case_id") != case_id:
        raise ValueError("exact source case identity differs")
    if context.get("diagnostic_fixture") is not True or trace.get("diagnostic_fixture") is not True:
        receipt = attempt / "original-receipt.json"
        if not receipt.is_file():
            raise ValueError("Missing required source: original-receipt.json")
        return observe(case_id, context_path, trace_path, receipt)
    rows = trace.get("frames")
    if not isinstance(rows, list) or len(rows) != 900:
        raise ValueError("diagnostic 900-frame trace required")
    if context.get("assignment_id") != case_id.rsplit("__", 1)[0]:
        raise ValueError("diagnostic assignment identity differs")
    lanes = context.get("same_direction_lane_ids")
    if not isinstance(lanes, list) or len(lanes) < 2 or context.get("extreme_left_lane_id") not in lanes:
        raise ValueError("diagnostic two-lane source missing")
    limit = context.get("posted_limit_mps")
    if not isinstance(limit, (int, float)) or limit <= 0:
        raise ValueError("diagnostic posted-limit source missing")
    samples = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or row.get("time_s") != index / 20:
            raise ValueError("diagnostic frame identity differs")
        for name in ("ego_lane_id", "rear_lane_id", "ego_speed_mps", "rear_speed_mps",
                     "rear_to_ego_signed_gap_m", "sign_present_readback"):
            if name not in row:
                raise ValueError("diagnostic encounter observation missing: " + name)
        if row["ego_lane_id"] not in lanes or row["rear_lane_id"] not in lanes:
            raise ValueError("diagnostic lane identity missing")
        samples.append({**row, "ego_below_posted_limit": row["ego_speed_mps"] < limit,
                        "faster_rear_same_extreme_left_lane":
                            row["ego_lane_id"] == row["rear_lane_id"] == context["extreme_left_lane_id"] and
                            row["rear_speed_mps"] > row["ego_speed_mps"]})
    crossing = next((samples[i]["frame"] for i in range(1, len(samples))
                     if samples[i-1]["rear_to_ego_signed_gap_m"] > 0 >= samples[i]["rear_to_ego_signed_gap_m"]
                     and samples[i-1]["faster_rear_same_extreme_left_lane"]), None)
    return {"assignment_id": context["assignment_id"], "case_id": case_id,
            "posted_limit_mps": limit, "extreme_left_lane_id": context["extreme_left_lane_id"],
            "hov_designation_state_source_label": context["hov_designation_state"],
            "hov_compliance_state_source_label": context["hov_compliance_state"],
            "original_hov_occupancy_count": context["original_hov_occupancy_count"],
            "first_rear_gap_crossing_frame": crossing, "samples": samples,
            "knowledge_judgment": "unresolved", "continued_operation_judgment": "unresolved",
            "hov_legal_exception_judgment": "unresolved", "physical_acceptance": "unverified"}


def controlled_access_lane_observation(measured):
    return {"extreme_left_lane_id": measured["extreme_left_lane_id"],
            "first_ego_lane_id": measured["samples"][0]["ego_lane_id"],
            "last_ego_lane_id": measured["samples"][-1]["ego_lane_id"],
            "original_site_legal_status": "unresolved"}


def posted_limit_knowledge_observation(measured):
    return {"posted_limit_mps": measured["posted_limit_mps"],
            "first_below_limit_frame": next((r["frame"] for r in measured["samples"]
                                             if r["ego_below_posted_limit"]), None),
            "knowledge_judgment": "unresolved"}


def faster_rear_overtaking_observation(measured):
    return {"first_rear_gap_crossing_frame": measured["first_rear_gap_crossing_frame"],
            "first_faster_rear_frame": next((r["frame"] for r in measured["samples"]
                                            if r["faster_rear_same_extreme_left_lane"]), None),
            "overtaking_legal_judgment": "unresolved"}


def continued_left_lane_observation(measured):
    return {"last_ego_lane_id": measured["samples"][-1]["ego_lane_id"],
            "continued_operation_judgment": "unresolved"}


def hov_qualification_observation(measured):
    return {"designation_state": measured["hov_designation_state_source_label"],
            "compliance_state": measured["hov_compliance_state_source_label"],
            "occupancy_count": measured.get("original_hov_occupancy_count"),
            "hov_legal_exception_judgment": "unresolved"}


def other_exception_observation(measured):
    return {"source_context_required": True,
            "city_and_hazard_exception_judgment": "unresolved"}


METHODS = (controlled_access_lane_observation, posted_limit_knowledge_observation,
           faster_rear_overtaking_observation, continued_left_lane_observation,
           hov_qualification_observation, other_exception_observation)


def build_report(attempt, case_id):
    context, trace = sources(attempt)
    measured = measured_source(attempt, case_id)
    bindings = {"context.json": sha(context), "trace.json": sha(trace)}
    measurements = {method.__name__: {"value": method(measured), "method": method.__name__,
                                       "sources": bindings} for method in METHODS}
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
        if name == "original_sign_exposure_s":
            value = next((r["time_s"] for r in rows if r["sign_present_readback"]), -1.0)
        elif name == "original_rear_speed_delta_mps":
            crossing = report["measurements"]["faster_rear_overtaking_observation"]["value"]["first_rear_gap_crossing_frame"]
            value = rows[crossing]["rear_speed_mps"] - rows[crossing]["ego_speed_mps"] if crossing is not None else 0.0
        elif name == "original_hov_occupancy_count":
            value = context["original_hov_occupancy_count"]
        else:
            value = None
        with path.open("x", encoding="utf-8") as stream:
            for index, row in enumerate(rows):
                if name == "controlled_access_and_lane_geometry":
                    item = {"lanes": context["same_direction_lane_ids"], "left": context["extreme_left_lane_id"]}
                elif name == "ego_rear_lane_speed_gap":
                    item = {key: row[key] for key in ("ego_lane_id", "rear_lane_id", "ego_speed_mps",
                                                       "rear_speed_mps", "rear_to_ego_signed_gap_m")}
                elif name == "posted_limit_and_knowledge":
                    item = {"posted_limit_mps": context["posted_limit_mps"], "knowledge": "unresolved"}
                elif name == "hov_designation_and_compliance":
                    item = {"designation": context["hov_designation_state"],
                            "compliance": context["hov_compliance_state"],
                            "occupancy": context["original_hov_occupancy_count"]}
                elif name == "other_exception_context":
                    item = {"city_or_hazard": context.get("exception_context_request"), "judgment": "unresolved"}
                elif name == "four_synchronized_camera_views":
                    item = {"frame": index, "views": ["overview", "approach", "reference_corner", "driver_reference"]}
                elif name in ("original_sign_exposure_s", "original_rear_speed_delta_mps", "original_hov_occupancy_count"):
                    item = value
                else:
                    raise ValueError("unsupported C380107 recording channel: " + name)
                stream.write(json.dumps({"time_s": index / 20, "value": item}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": str(path.relative_to(attempt))})
    (channels / "context.json").write_text(json.dumps({"original highway and HOV authority": {
        "source_kind": "synthetic CPU fixture" if report["diagnostic_fixture"] else "original Native source pending independent review",
        "physical_reviewed": False}}) + "\n")
    for channel in description["context_inputs"]:
        evidence.append({"name": channel["name"], "unit": channel["unit"], "reference": "channels/context.json"})
    requested = config.get("ego_target_speed_mps", 1.0)
    measured = rows[-1]["ego_speed_mps"]
    result = {"case_id": case_id, "measured_values": report["measurements"],
              "target_checks": [{"target": "authored engineering ego speed station",
                                 "requested": requested, "measured": measured,
                                 "method": "saved original ego speed trace",
                                 "tolerance": 4.0, "matched": abs(requested - measured) <= 4,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": {"context.json": sha(attempt / "context.json"),
                                                    "trace.json": sha(attempt / "trace.json")}}],
              "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved source assessment pending independent physical review",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {"controlled_access_lane": report["measurements"]["controlled_access_lane_observation"]["value"],
                                       "faster_rear": report["measurements"]["faster_rear_overtaking_observation"]["value"]}}
    result = physical_result(attempt, result)
    for name in ("original_sign_exposure_s", "original_rear_speed_delta_mps", "original_hov_occupancy_count"):
        value = next(json.loads(line)["value"] for line in (channels / (name + ".jsonl")).read_text().splitlines())
        result["realized_observables"][name] = {
            "value": value, "unit": next(c["unit"] for c in description["channels"] if c["name"] == name),
            "method": "source-bound original 20 Hz readback",
            "time_window": "all 900 original ticks", "statistic": "first",
            "reference": "channels/" + name + ".jsonl", "sample_window_s": [0.0, 44.95]}
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh analysis report required")
    config = json.loads((args.attempt / "config.json").read_text())
    report = build_report(args.attempt, config["selected_case_id"])
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
