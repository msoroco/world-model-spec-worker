"""Saved-original business-alley activity finalizer without a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_original_attempt import audit
from alley_activity import measure_original_activity

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_NAMES = ("activity.jsonl", "activity-seal.json", "frame-map.json", "site.json", "actors.json")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + str(path))
    return path


def _rows(path):
    return [json.loads(line) for line in _require(path).read_text().splitlines() if line.strip()]


def measure_business_alley(source, case_id):
    """Derive observed activity only from a hash-sealed original Native episode."""
    source = Path(source)
    checked = audit(source, case_id)
    measured = measure_original_activity(source / "activity.jsonl", source / "activity-seal.json",
                                         case_id, diagnostic=checked["frame_count"] == 9)
    return checked, measured


def build(attempt):
    attempt = Path(attempt)
    config = json.loads(_require(attempt / "config.json").read_text())
    construction = json.loads(_require(attempt / "construction.json").read_text())
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("saved construction case differs")
    source = attempt / "original-attempt"
    for name in SOURCE_NAMES:
        if not (source / name).is_file() or (source / name).is_symlink():
            raise ValueError("Missing required source: original-attempt/" + name)
    checked, measured = measure_business_alley(source, case_id)
    frames = json.loads(_require(source / "frame-map.json").read_text())["frames"]
    activity = _rows(source / "activity.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    video = _rows(attempt / "video_frames.jsonl")
    expected_count = checked["frame_count"]
    if len(trace) != len(video) or len(video) != len(frames) or len(frames) != expected_count:
        raise ValueError("original business-alley episode incomplete")
    for index, (mapped, frame, state) in enumerate(zip(video, frames, activity)):
        if (mapped.get("video_frame") != index or mapped.get("carla_frame") != frame["native_frame"] or
                mapped.get("time_s") != frame["native_time_s"] or state["frame"] != index):
            raise ValueError("original business-alley frame join differs")
    for view in VIEWS:
        _require(attempt / (view + ".mkv"))
    plan = json.loads(_require(attempt / "case-plan.json").read_text())
    sources = {"original-attempt/" + name: _sha(source / name) for name in SOURCE_NAMES}
    outputs = {}
    for disposition in plan["requirement_dispositions"]:
        if case_id not in disposition["case_ids"]:
            continue
        index = disposition["disposition_index"]
        if index == 0:
            value = {"halt_intervals_s": measured["intervals_s"]["halt"],
                     "business_alley_frames": measured["business_alley_frames"],
                     "passenger_intervals_s": measured["intervals_s"]["passenger_contact"],
                     "driver_outside_intervals_s": measured["intervals_s"]["driver_outside"],
                     "stop_stand_park_judgment": "unreviewed"}
            inputs = ("activity.jsonl", "activity-seal.json", "frame-map.json")
        elif index == 1:
            value = {"goods_intervals_s": measured["intervals_s"]["goods_contact"],
                     "halt_intervals_s": measured["intervals_s"]["halt"],
                     "expeditiousness_judgment": "unreviewed"}
            inputs = ("activity.jsonl", "activity-seal.json", "actors.json")
        else:
            value = {"ordinance_applicable_frames": measured["ordinance_applicable_frames"],
                     "ordinance_judgment": "unreviewed"}
            inputs = ("activity.jsonl", "site.json")
        outputs["business_alley_requirement_" + str(index)] = {
            "method": "measure_business_alley", "value": value,
            "sources": {"original-attempt/" + name: sources["original-attempt/" + name]
                        for name in inputs}}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": outputs, "analysis_complete": True,
              "legal_verdict_claimed": False, "source_audit": checked,
              "limitations": ["Stop, stand, park and expeditiousness need independent legal review.",
                              "Local ordinance applicability needs source review."]}
    return report, construction, config, activity, video, measured, sources


def write_result(attempt, built):
    from worker_exchange.native_output import validate_result
    report, construction, config, activity, video, measured, sources = built
    attempt = Path(attempt)
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    names = [item["name"] for item in construction["recording_description"]["channels"]]
    values = {
        "original_alley_business_district": [row["in_business_alley"] for row in activity],
        "original_vehicle_halt_history": [{"speed_mps": row["ego_speed_mps"], "xy_m": row["ego_xy_m"]} for row in activity],
        "original_passenger_activity": [{"contact": row["passenger_contact"], "door_open": row["door_open"]} for row in activity],
        "original_goods_activity": [row["goods_contact"] for row in activity],
        "original_driver_presence": [row["driver_in_vehicle"] for row in activity],
        "local_ordinance_applicability": [row["ordinance_reviewed_applicable"] for row in activity],
        "four_original_camera_streams": [dict(video_frame=row["video_frame"], native_frame=row["carla_frame"]) for row in video],
    }
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        if name not in values or len(values[name]) != len(activity):
            raise ValueError("mandatory original business-alley channel absent: " + name)
        destination = channels / (name + ".jsonl")
        destination.write_text("\n".join(json.dumps({"time_s": i / 20, "value": value}, sort_keys=True)
                                         for i, value in enumerate(values[name])) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(destination.relative_to(attempt))})
    if set(names) != set(values):
        raise ValueError("original business-alley channel inventory differs")
    context = channels / "context.json"
    site = json.loads((attempt / "original-attempt/site.json").read_text())
    context.write_text(json.dumps({
        "reviewed_business_alley_packet": {"source_sha256": sources["original-attempt/site.json"],
                                           "source_kind": site["source_kind"],
                                           "business_district_reviewed": site.get("business_district_reviewed", False)},
        "legal_review": "unreviewed"}, sort_keys=True) + "\n")
    for item in construction["recording_description"].get("context_inputs", []):
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(attempt))})
    intervals = measured["intervals_s"]
    target = {"target": "original business-alley vehicle halt and selected actor activity",
              "requested": config["variant"],
              "measured": {"halt_intervals_s": intervals["halt"],
                           "passenger_intervals_s": intervals["passenger_contact"],
                           "goods_intervals_s": intervals["goods_contact"]},
              "method": "measure_business_alley", "tolerance": None,
              "matched": False, "physical_cause_confirmed": False,
              "cause_evidence": sources}
    result = {"case_id": config["selected_case_id"],
              "measured_values": {key: value["value"] for key, value in report["measurements"].items()},
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": bool(intervals["halt"]), "maneuver_completed": False,
              "termination_reason": "Original activity measured; physical and legal review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence,
              "realized_observables": {"sampled_halt_duration_s": {
                  "value": sum(end - start for start, end in intervals["halt"]),
                  "unit": "s", "method": "source-sealed 20 Hz activity",
                  "time_window": "full diagnostic or original episode", "statistic": "sum of halt intervals",
                  "reference": "channels/original_vehicle_halt_history.jsonl", "source_refs": sources}},
              "physical_checks": {"setup": {"status": "unverified", "reason": "business-district source review pending"},
                                  "target": {"status": "unverified", "reason": "observed activity does not prove statutory cause"},
                                  "maneuver": {"status": "unverified", "reason": "original physical review pending"}},
              "provenance_kind": "synthetic_fixture" if report["source_audit"]["diagnostic_fixture"] else "native",
              "diagnostic_fixture": report["source_audit"]["diagnostic_fixture"],
              "physical_acceptance_claimed": False}
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.attempt / "result.json").exists() or args.output.exists():
        raise ValueError("refusing to overwrite original business-alley analysis")
    built = build(args.attempt)
    result = write_result(args.attempt, built)
    report = built[0]
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
