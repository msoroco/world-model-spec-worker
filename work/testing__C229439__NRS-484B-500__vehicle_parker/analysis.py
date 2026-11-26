"""Saved-only parking measurement and Native result finalization."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking_place import ASSIGNMENT, measure


SOURCES = ("parking-history.jsonl", "parking-context.json", "video_frames.jsonl", "trace.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified(attempt, name, acquisition):
    path = Path(attempt) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    record = acquisition.get(name, {})
    if record.get("kind") != "original_native" or record.get("sha256") != sha(path):
        raise ValueError("missing or stale original Native source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def measure_saved(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text(encoding="utf-8"))
    paths = {name: verified(attempt, name, acquisition) for name in SOURCES}
    history = rows(paths["parking-history.jsonl"])
    mapping = rows(paths["video_frames.jsonl"])
    trace = rows(paths["trace.jsonl"])
    if not history or len(history) != len(mapping) or len(trace) != len(mapping):
        raise ValueError("original parking, trace and camera frame counts differ")
    for event, video, telemetry in zip(history, mapping, trace):
        if ((event.get("frame"), event.get("time_s")) !=
                (video.get("carla_frame"), video.get("time_s")) or
                (event.get("frame"), event.get("time_s")) !=
                (telemetry.get("frame"), telemetry.get("time_s"))):
            raise ValueError("original parking, trace and camera frame identities differ")
    context = json.loads(paths["parking-context.json"].read_text(encoding="utf-8"))
    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    if context.get("case_id") != config.get("selected_case_id") or context.get("assignment_id") != ASSIGNMENT:
        raise ValueError("original parking context differs from exact case")
    if any(row.get("vehicle_actor_id") != context.get("vehicle_actor_id") or
           row.get("device_actor_id") != context.get("device_actor_id") for row in history):
        raise ValueError("original vehicle or erected device identity differs")
    packet = dict(context)
    packet.update(original_trace_id=sha(paths["parking-history.jsonl"]),
                  frames=[{"time_s": row["time_s"], "speed_mps": row["speed_mps"],
                           "vehicle_footprint": row["vehicle_footprint"]} for row in history])
    packet_path = attempt / "parking-measurement-input.json"
    if packet_path.exists():
        raise ValueError("prior measurement input exists in saved stage")
    packet_path.write_text(json.dumps(packet, allow_nan=False) + "\n", encoding="utf-8")
    measurement = measure(packet_path)
    requested_inside = config["case"]["requested_footprint"] == "inside"
    relevant = (measurement["stationary_wholly_inside_frames"] if requested_inside else
                [o["frame_index"] for o in measurement["observations"]
                 if o["speed_mps"] <= 0.1 and o["body_wholly_outside_place"]])
    return {"format": "worker-parking-measurement", "case_id": config["selected_case_id"],
            "frame_count": len(history), "requested_conduct": config["case"]["requested_conduct"],
            "requested_footprint": config["case"]["requested_footprint"],
            "place_context_for_review": config["case"]["place_context_for_review"],
            "stationary_requested_footprint_frames": relevant,
            "stationary_wholly_inside_episodes": measurement["stationary_wholly_inside_episodes"],
            "body_observations": measurement["observations"],
            "sources": {name: acquisition[name]["sha256"] for name in SOURCES},
            "source_context": context,
            "legal_conduct_or_place_character": "unresolved"}


def saved_result(attempt, value):
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    description = construction["recording_description"]
    history = rows(attempt / "parking-history.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    context = json.loads((attempt / "parking-context.json").read_text(encoding="utf-8"))
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    stream_values = {
        "vehicle_body_history": [r["vehicle_footprint"] for r in history],
        "vehicle_speed_and_control_history": [{"speed_mps": r["speed_mps"],
            "control_command": r["control_command"], "phase": r["phase"]} for r in history],
        "designated_place_geometry": [context["designated_place_polygon"]] * len(history),
        "device_identity_history": [{"device_actor_id": r["device_actor_id"],
             "device_id": context["device_id"]} for r in history],
        "place_context_history": [context] * len(history),
        "camera_frame_map": mapping,
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in stream_values:
            raise ValueError("unsupported selected parking channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for row, sample in zip(history, stream_values[name]):
                stream.write(json.dumps({"time_s": row["time_s"], "value": sample},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_path = channels / "context.json"
    context_path.write_text(json.dumps({
        "official_device_context": {"device_id": context["device_id"],
                                    "device_actor_id": context["device_actor_id"],
                                    "authority_source": context["official_authority_source"]},
        "designated_extent_context": {"place_id": context["designated_place_id"],
                                       "polygon": context["designated_place_polygon"]},
        "hazard_or_congestion_context": {"status_for_review": context["hazard_or_congestion_status"],
                                         "source": context["hazard_or_congestion_source"]}},
        allow_nan=False) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    target_met = bool(value["stationary_requested_footprint_frames"])
    result = {"case_id": config["selected_case_id"], "measured_values": value,
              "target_checks": [{"target": "observed stationary vehicle in requested footprint",
                "requested": True, "measured": target_met, "method": "original body and speed frames",
                "tolerance": 0, "matched": target_met, "physical_cause_confirmed": False,
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
        "designated_parking_measurement": {"value": value, "method": "measure_saved",
                                            "sources": value["sources"]}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Actual device authority, place character, conduct and pixels require independent review."],
        "analysis_complete": True, "legal_verdict_claimed": False}
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                                 encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
