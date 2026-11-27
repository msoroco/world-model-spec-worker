"""Saved-only angle-parking finalizer; original sources are never repaired."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from angle_measurement import measure

ASSIGNMENT = "testing__C377875__NRS-484B-460__motor_vehicle_driver"
SOURCES = ("angle-history.jsonl", "angle-context.json", "video_frames.jsonl", "trace.jsonl",
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
    history = rows(paths["angle-history.jsonl"])
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
    context = json.loads(paths["angle-context.json"].read_text(encoding="utf-8"))
    if (context.get("assignment_id") != ASSIGNMENT or context.get("case_id") != cfg["selected_case_id"]
            or context.get("site_sha256") != sha(paths["reviewed-site/site.json"])
            or site.get("case_id") != cfg["selected_case_id"]
            or any(row.get("vehicle_actor_id") != context.get("vehicle_actor_id")
                   or row.get("device_actor_id") != context.get("official_device_actor_id") for row in history)):
        raise ValueError("original context, site or actor identity differs")
    device_path = attempt / "reviewed-site" / site["sources"]["official_device"]["path"]
    device = json.loads(device_path.read_text(encoding="utf-8"))
    roadway_path = attempt / "reviewed-site" / site["sources"]["roadway"]["path"]
    roadway = json.loads(roadway_path.read_text(encoding="utf-8"))
    purpose_path = attempt / "reviewed-site" / site["sources"]["purpose"]["path"]
    purpose = json.loads(purpose_path.read_text(encoding="utf-8"))
    if (device.get("indicated_angle_degrees") != context.get("indicated_angle_degrees")
            or roadway.get("curb_edge_xy") != context.get("curb_edge_xy")):
        raise ValueError("original device or curb differs from Native context")
    packet = {"source_kind": "diagnostic_native_shape" if fixture else "original_native",
              "diagnostic_fixture": fixture, "assignment_id": ASSIGNMENT,
              "case_id": cfg["selected_case_id"],
              "capture_source_sha256": sha(acquisition_path),
              "device_source_sha256": sha(device_path),
              "frame_map_sha256": sha(paths["video_frames.jsonl"]),
              "device": device, "highway_source_review": roadway.get("highway_status"),
              "curb_edge_xy": roadway.get("curb_edge_xy"),
              "halt_purpose_review": purpose, "frames": history}
    value = measure(packet)
    value["sources"] = {name: acquisition[name]["sha256"] for name in SOURCES}
    return value


def saved_result(attempt, value):
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    cfg = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    description = construction["recording_description"]
    history = rows(attempt / "angle-history.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    context = json.loads((attempt / "angle-context.json").read_text(encoding="utf-8"))
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    streams = {
        "vehicle_body_angle_history": [{"body_yaw_degrees": r["body_yaw_degrees"],
                                        "vehicle_vertices": r["vehicle_vertices"],
                                        "position_xy": r["position_xy"]} for r in history],
        "curb_edge_geometry": [context["curb_edge_xy"]] * len(history),
        "official_device_indication": [context["indicated_angle_degrees"]] * len(history),
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
        "official_device_source_context": {
            "source_hashes": value["sources"],
            "indicated_angle_degrees": context["indicated_angle_degrees"]},
        "highway_and_halt_context": {
            "curb_edge_xy": context["curb_edge_xy"],
            "requested_activity": context["requested_activity"]}},
        allow_nan=False) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    stationary = value["halt_frame_count"] >= 2
    result = {"case_id": cfg["selected_case_id"], "measured_values": value,
              "target_checks": [{"target": "observed halt in source-bound official-device governed area",
                "requested": True, "measured": stationary,
                "method": "original body yaw, speed, control, curb and device frames",
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
        "original_device_indicated_body_angle": {"value": value,
            "method": "measure_saved", "sources": value["sources"]}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Actual official status, governed-space placement, halt classification and pixels require independent original-source review."],
        "analysis_complete": True, "legal_verdict_claimed": False}
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
