"""Saved-only angle-parking finalizer; original sources are never repaired."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from orientation_measurement import measure
from orientation_site import load_site

ASSIGNMENT = "testing__C377875__LVMC-11-52-070__motor_vehicle_driver"
SOURCES = ("orientation-history.jsonl", "orientation-context.json", "video_frames.jsonl", "trace.jsonl",
           "reviewed-site/site.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def verified(attempt, name, acquisition):
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    ref = acquisition.get(name, {})
    if ref.get("kind") != "original_native" or ref.get("sha256") != sha(path):
        raise ValueError("missing or stale original Native source: " + name)
    return path


def measure_saved(attempt):
    attempt = Path(attempt)
    acquisition_path = attempt / "acquisition.json"
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    fixture = (attempt / "fixture-provenance.json").is_file()
    paths = {name: verified(attempt, name, acquisition) for name in SOURCES}
    site = json.loads(paths["reviewed-site/site.json"].read_text(encoding="utf-8"))
    for ref in site.get("sources", {}).values():
        verified(attempt, "reviewed-site/" + ref["path"], acquisition)
    load_site(paths["reviewed-site/site.json"], cfg_case_id(attempt))
    history = rows(paths["orientation-history.jsonl"])
    mapping = rows(paths["video_frames.jsonl"])
    trace = rows(paths["trace.jsonl"])
    cfg = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    if not history or len(history) != len(mapping) or len(trace) != len(mapping):
        raise ValueError("original angle, camera and trace frame counts differ")
    if len(history) != cfg["duration_s"] * cfg["rate_hz"] and not fixture:
        raise ValueError("original capture duration differs from exact 20 Hz contract")
    for event, video, telemetry in zip(history, mapping, trace):
        if event.get("frame") != video.get("carla_frame") or event.get("frame") != telemetry.get("frame") or event.get("time_s") != video.get("time_s") or event.get("time_s") != telemetry.get("time_s"):
            raise ValueError("original angle, camera and trace frame identities differ")
    context = json.loads(paths["orientation-context.json"].read_text(encoding="utf-8"))
    if (context.get("assignment_id") != ASSIGNMENT or context.get("case_id") != cfg["selected_case_id"]
            or context.get("site_sha256") != sha(paths["reviewed-site/site.json"])
            or site.get("case_id") != cfg["selected_case_id"]
            or any(row.get("vehicle_actor_id") != context.get("vehicle_actor_id")
                   or row.get("marking_actor_id") != context.get("marking_actor_id") for row in history)):
        raise ValueError("original context, site or actor identity differs")
    marking_path = attempt / "reviewed-site" / site["sources"]["marking"]["path"]
    marking = json.loads(marking_path.read_text(encoding="utf-8"))
    authority_path = attempt / "reviewed-site" / site["sources"]["authority"]["path"]
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    roadway_path = attempt / "reviewed-site" / site["sources"]["roadway"]["path"]
    roadway = json.loads(roadway_path.read_text(encoding="utf-8"))
    purpose_path = attempt / "reviewed-site" / site["sources"]["purpose"]["path"]
    purpose = json.loads(purpose_path.read_text(encoding="utf-8"))
    if (roadway.get("lawful_traffic_vector_xy") != context.get("lawful_traffic_vector_xy")
            or roadway.get("lawful_direction_status") != context.get("lawful_direction_status")
            or marking.get("permission_indicated") is not True
            or authority.get("angle_parking_permitted") is not True
            or purpose.get("category") != cfg["case"]["activity_request"]):
        raise ValueError("original permission or lawful traffic direction differs from Native context")
    packet = {"source_kind": "diagnostic_native_shape" if fixture else "original_native",
              "diagnostic_fixture": fixture, "assignment_id": ASSIGNMENT,
              "case_id": cfg["selected_case_id"],
              "capture_source_sha256": sha(acquisition_path),
              "marking_source_sha256": sha(marking_path),
              "frame_map_sha256": sha(paths["video_frames.jsonl"]),
              "marking": marking, "roadway_source_review": roadway.get("highway_status"),
              "lawful_direction_status": roadway.get("lawful_direction_status"),
              "authority": authority,
              "lawful_traffic_vector_xy": roadway.get("lawful_traffic_vector_xy"),
              "purpose_review": purpose, "frames": history}
    value = measure(packet)
    value["sources"] = {name: acquisition[name]["sha256"] for name in SOURCES}
    return value


def cfg_case_id(attempt):
    return json.loads((attempt / "config.json").read_text(encoding="utf-8"))["selected_case_id"]


def saved_result(attempt, value):
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    cfg = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    description = construction["recording_description"]
    history = rows(attempt / "orientation-history.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    context = json.loads((attempt / "orientation-context.json").read_text(encoding="utf-8"))
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    streams = {
        "vehicle_front_orientation_history": [{"body_yaw_degrees": r["body_yaw_degrees"],
                                        "vehicle_vertices": r["vehicle_vertices"],
                                        "position_xy": r["position_xy"]} for r in history],
        "lawful_traffic_direction": [context["lawful_traffic_vector_xy"]] * len(history),
        "engineer_permission_marking": [{"marking_source_sha256": context["marking_source_sha256"],
                                          "permission_indicated": True}] * len(history),
        "halt_purpose_and_service": [{"halt_observed": r["halt_observed"],
                                      "control_state": r["control_state"],
                                      "requested_activity": r["requested_activity"]} for r in history],
        "four_synchronized_camera_streams": mapping,
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in streams:
            raise ValueError("unsupported angle-parking channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for event, sample in zip(history, streams[name]):
                stream.write(json.dumps({"time_s": event["time_s"], "value": sample}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_path = channels / "context.json"
    context_path.write_text(json.dumps({
        "engineer_permission_context": {
            "source_hashes": value["sources"],
            "lawful_traffic_vector_xy": context["lawful_traffic_vector_xy"]},
        "standing_parking_context": {
            "lawful_direction_status": context["lawful_direction_status"],
            "requested_activity": context["requested_activity"]}},
        allow_nan=False) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    stationary = value["halt_frame_count"] >= 2
    result = {"case_id": cfg["selected_case_id"], "measured_values": value,
              "target_checks": [{"target": "observed standing or parking in Engineer-permitted and marked angle-parking area",
                "requested": True, "measured": stationary,
                "method": "original front yaw, speed, control, lawful lane direction and marking frames",
                "tolerance": 0, "matched": stationary,
                "physical_cause_confirmed": False, "cause_evidence": value["sources"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "Saved physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    value = measure_saved(args.attempt)
    result = saved_result(args.attempt, value)
    Path(args.attempt, "result.json").write_text(json.dumps(result, indent=2,
                                                     allow_nan=False) + "\n", encoding="utf-8")
    report = {"format": "worker-analysis-report", "measurements": {
        "original_front_vs_lawful_direction": {"value": value,
            "method": "measure_saved", "sources": value["sources"]}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Actual Engineer permission, marked extent, lawful traffic direction, standing/parking classification and pixels require independent original-source review."],
        "analysis_complete": True, "legal_verdict_claimed": False}
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
