"""Saved-only one-way parking finalizer; no CARLA imports or source repair."""

import argparse
import hashlib
import json
from pathlib import Path

from parking_measurements import ASSIGNMENT_ID, measure


SOURCES = ("parking-history.jsonl", "parking-context.json", "video_frames.jsonl", "trace.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def verified(attempt, name, acquisition, fixture):
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    ref = acquisition.get(name, {})
    if ref.get("kind") != "original_native" or ref.get("sha256") != sha(path):
        raise ValueError("missing or stale original Native source: " + name)
    return path


def measure_saved(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text(encoding="utf-8"))
    fixture = (attempt / "fixture-provenance.json").is_file()
    paths = {name: verified(attempt, name, acquisition, fixture) for name in SOURCES}
    history = rows(paths["parking-history.jsonl"])
    mapping = rows(paths["video_frames.jsonl"])
    trace = rows(paths["trace.jsonl"])
    if not history or len(history) != len(mapping) or len(trace) != len(mapping):
        raise ValueError("original parking, camera and trace frame counts differ")
    for event, video, telemetry in zip(history, mapping, trace):
        if (event.get("frame") != video.get("carla_frame") or
                event.get("frame") != telemetry.get("frame") or
                event.get("time_s") != video.get("time_s") or
                event.get("time_s") != telemetry.get("time_s")):
            raise ValueError("original parking, camera and trace frame identities differ")
    context = json.loads(paths["parking-context.json"].read_text(encoding="utf-8"))
    cfg = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    if (context.get("case_id") != cfg.get("selected_case_id") or
            context.get("assignment_id") != ASSIGNMENT_ID or
            any(row.get("vehicle_actor_id") != context.get("vehicle_actor_id") or
                row.get("device_actor_id") != context.get("device_actor_id") for row in history)):
        raise ValueError("original context or actor identity differs")
    receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": cfg["selected_case_id"],
               "source_kind": "diagnostic_native_shape" if fixture else "original_native_capture",
               "diagnostic_fixture": fixture,
               "context_sha256": sha(paths["parking-context.json"]),
               "trace_sha256": sha(paths["parking-history.jsonl"]),
               "fps": 20, "frame_count": len(history)}
    receipt_path = attempt / "oneway-measurement-receipt.json"
    receipt_path.write_text(json.dumps(receipt, allow_nan=False) + "\n", encoding="utf-8")
    value = measure(cfg["selected_case_id"], paths["parking-context.json"],
                    paths["parking-history.jsonl"], receipt_path,
                    allow_diagnostic=fixture)
    value["sources"] = {name: acquisition[name]["sha256"] for name in SOURCES}
    return value


def saved_result(attempt, value):
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    cfg = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    description = construction["recording_description"]
    history = rows(attempt / "parking-history.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    context = json.loads((attempt / "parking-context.json").read_text(encoding="utf-8"))
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    stream_values = {
        "vehicle_body_side_history": [{"vertices": r["vehicle_vertices"],
                                        "position_m": r["position_m"]} for r in history],
        "vehicle_speed_and_control_history": [{"speed_mps": r["speed_mps"],
            "control_command": r["control_command"], "control_state": r["control_state"]}
                                               for r in history],
        "roadway_direction_context": [context] * len(history),
        "device_permission_context": [context] * len(history),
        "parking_person_and_purpose_context": [context] * len(history),
        "camera_frame_map": mapping,
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in stream_values:
            raise ValueError("unsupported one-way parking channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for row, sample in zip(history, stream_values[name]):
                stream.write(json.dumps({"time_s": row["time_s"], "value": sample},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_path = channels / "context.json"
    context_path.write_text(json.dumps({
        "roadway_restriction_context": {
            "one_way_restriction": context["one_way_restriction"],
            "marked_lane_count": context["marked_lane_count"],
            "roadway_polygon_xy": context["roadway_polygon_xy"]},
        "official_device_context": {"device_kind": context["device_kind"],
                                     "device_actor_id": context["device_actor_id"]},
        "person_and_purpose_context": {
            "person_source": context["parking_person_source"],
            "purpose_source": context["halt_purpose_source"]},
        "source_hashes": value["sources"]}, allow_nan=False) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    observed_stationary = any(row["speed_mps"] <= .1 and
                              row["control_state"] in ("stop", "stand", "park")
                              for row in history)
    result = {"case_id": cfg["selected_case_id"], "measured_values": value,
              "target_checks": [{"target": "observed stationary vehicle with source-bound roadway and device",
                "requested": True, "measured": observed_stationary,
                "method": "original body, speed and control frames", "tolerance": 0,
                "matched": observed_stationary, "physical_cause_confirmed": False,
                "cause_evidence": value["sources"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "Saved physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv",
                                   "driver_reference.mkv"],
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
        "oneway_parking_measurement": {"value": value,
                                      "method": "measure_saved", "sources": value["sources"]}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Actual one-way restriction, device authority, governed space, activity and pixels require independent review."],
        "analysis_complete": True, "legal_verdict_claimed": False}
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                                 encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
