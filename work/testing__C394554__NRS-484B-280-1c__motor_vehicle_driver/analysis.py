"""Saved-only, source-hashed transit-stop measurement; no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from road_scene import load_site, measure as measure_sample


REQUIRED = ("transit-site.json", "map.xodr", "encounter-history.jsonl", "video_frames.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified(root, name, acquisition):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    source = acquisition.get(name, {})
    if source.get("kind") != "original_native" or source.get("sha256") != sha(path):
        raise ValueError("missing or stale original Native source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(attempt):
    root = Path(attempt)
    acquisition = json.loads((root / "acquisition.json").read_text())
    paths = {name: verified(root, name, acquisition) for name in REQUIRED}
    site = load_site(paths["transit-site.json"])
    history = rows(paths["encounter-history.jsonl"])
    frame_map = rows(paths["video_frames.jsonl"])
    if len(history) < 2 or len(history) != len(frame_map):
        raise ValueError("incomplete original transit encounter or frame join")
    first_observation = first_brake = None
    previous = None
    measurements = []
    phases = set()
    for row, frame in zip(history, frame_map):
        identity = row.get("frame"), row.get("time_s")
        if type(identity[0]) is not int or type(identity[1]) not in (int, float) or not math.isfinite(identity[1]):
            raise ValueError("invalid original encounter frame identity")
        if (frame.get("carla_frame"), frame.get("time_s")) != identity:
            raise ValueError("original encounter and camera frame identities differ")
        if previous and (identity[0] <= previous[0] or identity[1] <= previous[1]):
            raise ValueError("original encounter frame/time order changed")
        previous = identity
        value = measure_sample(site, row)
        phases.add(value["passenger_phase"])
        for key in ("pedestrian_stop_distance_m", "pedestrian_bus_door_region_gap_m"):
            if abs(row.get(key, float("inf")) - value[key]) > 0.05:
                raise ValueError("reported transit geometry differs from original bodies")
        if value["driver_observation_event"] and first_observation is None:
            first_observation = {"frame": identity[0], "time_s": identity[1],
                                 "source": value["driver_observation_event"]["source"]}
        if value["ego_brake"] > 0 and first_brake is None:
            first_brake = {"frame": identity[0], "time_s": identity[1]}
        if type(row.get("contact_event")) is not bool:
            raise ValueError("original contact readback absent")
        measurements.append(value)
    if len(phases) != 1:
        raise ValueError("passenger phase changed within exact case")
    response_delay = (first_brake["time_s"] - first_observation["time_s"]
                      if first_brake and first_observation else None)
    if response_delay is not None and response_delay < 0:
        raise ValueError("brake predates original observation event")
    first_gap = measurements[0]["pedestrian_bus_door_region_gap_m"]
    last_gap = measurements[-1]["pedestrian_bus_door_region_gap_m"]
    if not all(math.isfinite(value) for value in (first_gap, last_gap)):
        raise ValueError("invalid original boarding geometry")
    value = {"format": "worker-transit-pedestrian-measurements",
             "frame_count": len(history), "passenger_phase": phases.pop(),
             "first_observation": first_observation, "first_brake": first_brake,
             "observed_response_delay_s": response_delay,
             "first_bus_door_region_gap_m": first_gap,
             "last_bus_door_region_gap_m": last_gap,
             "door_approach_m": first_gap - last_gap,
             "minimum_pedestrian_stop_distance_m": min(item["pedestrian_stop_distance_m"] for item in measurements),
             "contact_frames": [row["frame"] for row in history if row["contact_event"]],
             "sources": {name: acquisition[name]["sha256"] for name in REQUIRED},
             "actual_bus_door_verified": False,
             "legal_near_stop_verdict": "unresolved",
             "legal_boarding_verdict": "unresolved",
             "legal_proper_caution_verdict": "unresolved"}
    return value, history, frame_map, site


def build_report(attempt):
    value, _, _, _ = measure(attempt)
    return {"format": "worker-analysis-report",
            "measurements": {"transit_pedestrian_caution_measurement": {
                "value": value, "method": "measure", "sources": value["sources"]}},
            "limitations": ["The original bus-body region is a door-side proxy; actual door and boarding pixels require local review.",
                            "Scripted input is not human observation and proper caution is a legal judgment."],
            "analysis_complete": True, "legal_verdict_claimed": False}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, validate_result
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    construction = json.loads((root / "construction.json").read_text())
    planned = construction["recording_description"]
    value, history, frame_map, site = measure(root)
    output = root / "channels"
    output.mkdir(exist_ok=True)
    streams = {
        "ego_body_history": [row["ego_body_vertices_m"] for row in history],
        "pedestrian_body_history": [row["pedestrian_body_vertices_m"] for row in history],
        "bus_body_history": [row["bus_body_vertices_m"] for row in history],
        "ego_speed_and_brake_history": [{"speed_mps": row["ego_speed_mps"], "brake": row["ego_brake"]} for row in history],
        "driver_observation_input_history": [{"event": row.get("driver_observation_event")} for row in history],
        "passenger_phase_history": [row["passenger_phase"] for row in history],
        "transit_stop_context": [site["stop"] for _ in history],
        "bus_door_region_gap_history": [row["pedestrian_bus_door_region_gap_m"] for row in history],
        "contact_events": [row["contact_event"] for row in history],
        "camera_frame_map": frame_map}
    evidence = []
    for channel in planned["channels"]:
        name = channel["name"]
        if name not in streams:
            raise ValueError("unsupported recording channel: " + name)
        path = output / (name + ".jsonl")
        with path.open("x") as stream:
            for row, item in zip(history, streams[name]):
                stream.write(json.dumps({"time_s": row["time_s"], "value": item}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": str(path.relative_to(root))})
    context = output / "context.json"
    context.write_text(json.dumps({"transit_site_context": site,
                                   "driver_input_context": {"kind": "scripted-driver input",
                                                            "human_observation_claimed": False}},
                                  allow_nan=False) + "\n")
    for item in planned["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"], "reference": str(context.relative_to(root))})
    target = value["first_observation"] is not None
    result = {"case_id": config["selected_case_id"], "measured_values": value,
              "target_checks": [{"target": "source-recorded driver observation near physical transit stop",
                                 "requested": True, "measured": target, "method": "measure",
                                 "tolerance": 0, "matched": target,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": value["sources"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved transit source assessment pending physical review",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": planned, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(root, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    with (Path(args.attempt) / "result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    with Path(args.output).open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
