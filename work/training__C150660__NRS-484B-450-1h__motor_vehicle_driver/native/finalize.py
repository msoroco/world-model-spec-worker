"""Saved-only original safety-zone measurement; no legal verdict."""

import argparse
import hashlib
import json
from pathlib import Path

from safety_zone_geometry import FRAME_COUNT, measure_frame, measure_trace

SOURCES = ("zone_raw.json", "context-survey.json", "video_frames.jsonl",
           "trace.jsonl", "capture/evidence.jsonl", "road.xodr", "authored-road.xodr")
VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_original_review(attempt, survey, case):
    seal_path = attempt / "capture-seal.json"
    if not seal_path.is_file():
        raise ValueError("Original source review requires a sealed Native capture")
    seal = json.loads(seal_path.read_text())
    sources = seal.get("sources")
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "native" or
            seal.get("diagnostic_fixture") or seal.get("frames") != FRAME_COUNT or
            not seal.get("restoration", {}).get("restored") or
            not isinstance(sources, dict) or
            seal.get("source_digest") != hashlib.sha256(json.dumps(
                sources, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False).encode()).hexdigest()):
        raise ValueError("Original Native capture seal is invalid")
    sealed_names = (*SOURCES, *VIDEOS, "construction.json", "runner.py")
    for name in sealed_names:
        if sources.get(name) != sha(attempt / name):
            raise ValueError("Original source differs from sealed capture: " + name)
    if (survey.get("case_id") != case or
            not isinstance(survey.get("independent_reviewer"), str) or
            not survey["independent_reviewer"].strip() or
            survey.get("actual_pixels_reviewed") is not True or
            survey.get("zone_raw_sha256") != sources["zone_raw.json"] or
            survey.get("road_sha256") != sources["road.xodr"] or
            survey.get("video_frames_sha256") != sources["video_frames.jsonl"] or
            survey.get("video_sha256") != {name: sources[name] for name in VIDEOS}):
        raise ValueError("Original review is not independently bound to sealed sources")
    review_keys = ("safety_zone_official_status", "zone_marker_readback",
                   "adjacent_curb_readback", "halt_purpose", "traffic_conflict",
                   "applicable_law_direction", "officer_direction", "device_direction")
    if any(survey.get(key) is None for key in review_keys):
        raise ValueError("Original designation, curb or exception review incomplete")


def measure_safety_zone(rows, zone):
    return measure_trace(rows, zone)


def source_review(survey, keys):
    return {key: survey.get(key) for key in keys}


def finalize(attempt_path, output_path):
    attempt, output = Path(attempt_path), Path(output_path)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved result; use a fresh attempt")
    for name in (*SOURCES, *VIDEOS, "config.json", "construction.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case = config.get("selected_case_id")
    if case != construction.get("case_id") or case not in config.get("supported_case_ids", []):
        raise ValueError("Saved finalizer exact-case identity differs")
    raw = json.loads((attempt / "zone_raw.json").read_text())
    survey = json.loads((attempt / "context-survey.json").read_text())
    if raw.get("case_id") != case or survey.get("case_id") != case:
        raise ValueError("Original safety-zone source identity differs")
    if survey.get("review_kind") not in ("synthetic_diagnostic", "original_source_review"):
        raise ValueError("Original safety-zone context review kind missing")
    if survey["review_kind"] == "original_source_review":
        verify_original_review(attempt, survey, case)
    zone = raw.get("zone")
    rows = raw.get("frames")
    observed = measure_safety_zone(rows, zone)
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
    if len(frames) != FRAME_COUNT or len(trace) != FRAME_COUNT:
        raise ValueError("Requires full original trace/frame join")
    for index, (frame, pose, row) in enumerate(zip(frames, trace, rows)):
        if (frame.get("video_frame") != index or
                pose.get("frame") != frame.get("carla_frame") or
                row.get("native_frame") != frame.get("carla_frame") or
                abs(frame.get("time_s", -1) - pose.get("time_s", -2)) > 1e-6):
            raise ValueError("Original camera, actor and trace frame join differs")
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    diagnostic = survey["review_kind"] == "synthetic_diagnostic"
    source_kind = "synthetic_fixture" if diagnostic else "native"
    measurements = [{"frame": index, "time_s": row["time_s"],
                     **measure_frame(row["vehicle_footprint_corners_m"], zone),
                     "vehicle_stopped": row["vehicle_stopped"],
                     "speed_mps": row.get("speed_mps")}
                    for index, row in enumerate(rows)]
    values = {
        "safety_zone_geometry": {"method": "measure_safety_zone",
                                 "value": observed, "sources": source_hashes},
        "safety_zone_designation": {"method": "source_review",
                                     "value": {"zone_map_source": zone["zone_map_source"],
                                               "official_status": survey.get("safety_zone_official_status")},
                                     "sources": source_hashes},
        "curb_and_exception_context": {"method": "source_review",
                                       "value": source_review(survey, (
                                           "adjacent_curb_readback", "halt_purpose",
                                           "traffic_conflict", "applicable_law_direction",
                                           "officer_direction", "device_direction")),
                                       "sources": source_hashes},
    }
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for measured in measurements:
                if name == "drv.standing_or_parked":
                    value = measured["vehicle_stopped"]
                elif name == "st.safety_zone":
                    value = {"geometry": zone, "designation_review": survey.get("safety_zone_official_status")}
                elif name == "st.road_edge":
                    value = {"curb_y_m": zone["curb_y_m"],
                             "source": survey.get("adjacent_curb_readback")}
                elif name == "rel.occupies":
                    value = measured["fully_between_zone_and_curb"]
                elif name == "rel.centre_distance":
                    value = {"start_m": measured["distance_to_opposite_start_m"],
                             "end_m": measured["distance_to_opposite_end_m"]}
                elif name == "kin.position":
                    value = {"opposite_start_m": [zone["x_start_m"], zone["curb_y_m"]],
                             "opposite_end_m": [zone["x_end_m"], zone["curb_y_m"]],
                             "footprint": rows[measured["frame"]]["vehicle_footprint_corners_m"]}
                elif name == "drv.forced_halt":
                    value = {"traffic_conflict_review": survey.get("traffic_conflict"),
                             "halt_purpose_review": survey.get("halt_purpose")}
                elif name == "dev.human_direction":
                    value = {"officer_direction_review": survey.get("officer_direction")}
                elif name == "exception_context":
                    value = {key: survey.get(key) for key in (
                        "traffic_conflict", "applicable_law_direction",
                        "officer_direction", "device_direction")}
                else:
                    raise ValueError("Unsupported safety-zone channel: " + name)
                stream.write(json.dumps({"time_s": measured["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": "channels/" + path.name})
    report = {"format": "worker-analysis-report", "case_id": case,
              "measurements": values, "source_complete": True,
              "diagnostic_fixture": diagnostic, "physical_or_legal_acceptance": False}
    final_rows = measurements[-100:]
    rest = sum(bool(row["vehicle_stopped"]) for row in final_rows)
    requested_position = config["position_request"]
    if requested_position == "between":
        matched = all(row["fully_between_zone_and_curb"] for row in final_rows if row["vehicle_stopped"])
    else:
        desired_ft = float(config["requested_curb_end_gap_ft"])
        key = "distance_to_opposite_end_m" if requested_position == "past_end" else "distance_to_opposite_start_m"
        matched = all(abs(row[key] - desired_ft * .3048) <= .25 for row in final_rows if row["vehicle_stopped"])
    maneuver = rest >= 80 and matched
    physical_sources = {name: source_hashes[name] for name in
                        ("zone_raw.json", "trace.jsonl", "video_frames.jsonl", "road.xodr")}
    physical_checks = {
        "setup": {"status": "met" if not diagnostic else "unverified",
                  "method": "full 600-frame zone, curb, footprint and camera join",
                  "sources": physical_sources},
        "maneuver": {"status": ("met" if maneuver else "not_met") if not diagnostic else "unverified",
                     "method": "at least 80 of final 100 original samples at rest and engineering target position",
                     "sources": physical_sources, "final_rest_samples": rest,
                     "position_request": requested_position}}
    result = {"case_id": case, "measured_values": observed,
              "target_checks": [{"target": "observed safety-zone resting position",
                                 "requested": requested_position,
                                 "measured": measurements[-1],
                                 "method": "measure_safety_zone", "tolerance": 0.25,
                                 "matched": matched,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(SOURCES)}],
              "setup_confirmed": not diagnostic, "behavior_attempted": not diagnostic,
              "maneuver_completed": not diagnostic and maneuver,
              "physical_checks": physical_checks,
              "termination_reason": "Saved geometry measured; official zone, curb and exceptions require independent original-source review",
              "physical_failure_flags": ["Original zone designation, halt cause and actual pixels unverified"],
              "trace_reference": "trace.jsonl", "video_references": list(VIDEOS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "provenance_kind": source_kind, "diagnostic_fixture": diagnostic,
              "physical_acceptance_claimed": False, "accepted": False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
