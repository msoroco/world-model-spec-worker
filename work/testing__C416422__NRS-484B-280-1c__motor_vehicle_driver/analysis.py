"""Saved-only measurements of an original roadside pedestrian encounter.

This analyzer never converts engineering response timing into a legal verdict.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from road_scene import load_site, observed_encounter


REQUIRED = ("road-site.json", "map.xodr", "encounter-history.jsonl", "video_frames.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified(root, name, acquisition):
    path = Path(root) / name
    source = acquisition.get(name, {})
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    if source.get("kind") != "original_native" or source.get("sha256") != sha(path):
        raise ValueError("missing or stale original Native source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(attempt):
    root = Path(attempt)
    acquisition = json.loads((root / "acquisition.json").read_text())
    source_paths = {name: verified(root, name, acquisition) for name in REQUIRED}
    site = load_site(source_paths["road-site.json"])
    history = rows(source_paths["encounter-history.jsonl"])
    frame_map = rows(source_paths["video_frames.jsonl"])
    if len(history) < 2 or len(history) != len(frame_map):
        raise ValueError("incomplete original encounter or camera frame join")
    previous = None
    measured = []
    first_observation = None
    first_brake = None
    for row, frame in zip(history, frame_map):
        ident = row.get("frame"), row.get("time_s")
        if type(ident[0]) is not int or type(ident[1]) not in (int, float) or not math.isfinite(ident[1]):
            raise ValueError("invalid original encounter frame identity")
        if (frame.get("carla_frame"), frame.get("time_s")) != ident:
            raise ValueError("original encounter and camera frame identities differ")
        if previous and (ident[0] <= previous[0] or ident[1] <= previous[1]):
            raise ValueError("original encounter frame/time order changed")
        previous = ident
        value = observed_encounter(site, row)
        if abs(row.get("surface_gap_m", float("inf")) - value["surface_gap_m"]) > 0.05:
            raise ValueError("reported gap differs from original bodies")
        if value["driver_observation_event"] and first_observation is None:
            first_observation = {"frame": ident[0], "time_s": ident[1],
                                 "source": value["driver_observation_event"]["source"]}
        if value["ego_brake"] > 0 and first_brake is None:
            first_brake = {"frame": ident[0], "time_s": ident[1],
                           "gap_m": value["surface_gap_m"],
                           "ego_speed_mps": value["ego_speed_mps"]}
        contact = row.get("contact_event")
        if type(contact) is not bool:
            raise ValueError("original contact readback absent")
        measured.append({"frame": ident[0], "time_s": ident[1], **value,
                         "contact_event": contact})
    response_delay = (first_brake["time_s"] - first_observation["time_s"]
                      if first_observation and first_brake else None)
    if response_delay is not None and response_delay < 0:
        raise ValueError("brake predates original observation event")
    value = {"format": "worker-near-road-pedestrian-measurements",
             "frame_count": len(history), "first_observation": first_observation,
             "first_brake": first_brake, "observed_response_delay_s": response_delay,
             "minimum_surface_gap_m": min(item["surface_gap_m"] for item in measured),
             "contact_frames": [item["frame"] for item in measured if item["contact_event"]],
             "observed_ego_speed_range_mps": [min(item["ego_speed_mps"] for item in measured),
                                              max(item["ego_speed_mps"] for item in measured)],
             "sources": {name: acquisition[name]["sha256"] for name in REQUIRED},
             "road_edge_gap_m": min(item["road_edge_gap_m"] for item in measured),
             "pedestrian_bodily_off_road": all(item["pedestrian_bodily_off_road"] for item in measured),
             "legal_near_road_verdict": "unresolved",
             "legal_proper_caution_verdict": "unresolved"}
    return value, history, frame_map, site


def build_report(attempt):
    value, _, _, _ = measure(attempt)
    return {"format": "worker-analysis-report",
            "measurements": {"pedestrian_near_road_caution_measurement": {
                "value": value, "method": "measure", "sources": value["sources"]}},
            "limitations": ["Original driver input is distinct from human cognition; statutory near and proper caution remain unresolved."],
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
        "ego_speed_and_brake_history": [{"speed_mps": row["ego_speed_mps"],
                                         "brake": row["ego_brake"]} for row in history],
        "driver_observation_input_history": [{"event": row.get("driver_observation_event"),
                                              "input_present": row.get("driver_observation_event") is not None}
                                             for row in history],
        "road_boundary_context": [{"road": site["road"], "sidewalk": site["sidewalk"]} for _ in history],
        "participant_classification_context": [{"ego_class": row["ego_class"],
                                                  "pedestrian_class": row["pedestrian_class"]} for row in history],
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
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root))})
    context_path = output / "context.json"
    context_path.write_text(json.dumps({"road_site_context": site,
                                        "driver_input_context": {"kind": "scripted-driver input",
                                                                 "original_source_sha256": value["sources"]["encounter-history.jsonl"],
                                                                 "human_observation_claimed": False}}, allow_nan=False) + "\n")
    for item in planned["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(root))})
    target = value["first_observation"] is not None
    result = {"case_id": config["selected_case_id"], "measured_values": value,
              "target_checks": [{"target": "source-recorded driver input with pedestrian on reviewed off-road sidewalk",
                                 "requested": True, "measured": target, "method": "measure",
                                 "tolerance": 0, "matched": target,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": value["sources"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved source assessment pending physical review",
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
