"""Publish factual saved channels and a Native result from original frames.

This publication makes no legal decision. The local coordinator independently
validates its source streams, videos and Core conversion.
"""
from __future__ import annotations

import json
from pathlib import Path

from dual_green import require


CHANNELS = (
    "signal_head_history", "ego_body_history", "vehicle_body_history",
    "pedestrian_body_history", "intersection_geometry", "crosswalk_geometry",
    "lawful_presence_context", "original_lamp_pixels",
)
VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
          "driver_reference.mkv")


def publish(attempt, report):
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((root / "construction.json").read_text(encoding="utf-8"))
    description = construction["recording_description"]
    channels = {entry["name"]: entry for entry in description["channels"]}
    require(set(channels) == set(CHANNELS), "selected recording channels changed")
    require({entry["name"] for entry in description["context_inputs"]} ==
            {"site_source_survey"}, "selected site context changed")
    events = json.loads((root / "original-events.json").read_text(encoding="utf-8"))
    trace = [json.loads(line) for line in (root / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text(encoding="utf-8").splitlines()]
    site = json.loads((root / "site.json").read_text(encoding="utf-8"))
    require(len(events) >= 3 and len(trace) == len(events) == len(mapping),
            "selected original frame join incomplete")
    values = {name: [] for name in CHANNELS}
    for index, (event, point, frame) in enumerate(zip(events, trace, mapping)):
        require(frame["video_frame"] == index and event["frame"] == point["frame"] ==
                frame["carla_frame"] and abs(float(event["elapsed_seconds"]) -
                float(point["time_s"])) <= 1e-4 and abs(float(frame["time_s"]) -
                float(point["time_s"])) <= 1e-4,
                "selected original frame/time join differs")
        t = point["time_s"]
        users = event["other_users"]
        packet = {
            "signal_head_history": {"head_id": event["official_head_id"],
                                    "lit_aspects": event["lit_aspects"],
                                    "source": event["aspect_observation_source"]},
            "ego_body_history": {"position": point["position"],
                                 "heading_deg": point["heading_deg"],
                                 "speed_mps": point["speed_mps"]},
            "vehicle_body_history": [u for u in users if u["kind"] == "motor_vehicle"],
            "pedestrian_body_history": [u for u in users if u["kind"] == "pedestrian"],
            "intersection_geometry": site["intersection_polygon_xy"],
            "crosswalk_geometry": site["adjacent_crosswalk_polygon_xy"],
            "lawful_presence_context": {u["id"]: u["lawful_use_source"] for u in users},
            "original_lamp_pixels": {"source": event["aspect_observation_source"],
                                     "sha256": event["aspect_observation_sha256"]},
        }
        for name, value in packet.items():
            values[name].append({"time_s": t, "value": value})
    evidence = []
    for name in CHANNELS:
        path = root / (name + ".jsonl")
        require(not path.exists(), "selected channel already published")
        with path.open("x", encoding="utf-8") as stream:
            for row in values[name]:
                stream.write(json.dumps(row, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channels[name]["unit"],
                         "reference": path.name})
    context = root / "site-source-survey.json"
    require(not context.exists(), "selected context already published")
    context.write_text(json.dumps({"site_source_survey": site}, allow_nan=False) + "\n",
                       encoding="utf-8")
    evidence.append({"name": "site_source_survey", "unit": description[
        "context_inputs"][0]["unit"], "reference": context.name})
    exhibition = report["measurements"]["dual_aspect_observation"]["value"]
    requested = ["circular_green", "green_" + site["arrow_direction"] + "_arrow"]
    observed = next(e["lit_aspects"] for e in events if e["frame"] == exhibition[
        "first_exhibition_frame"])
    result = {
        "case_id": config["selected_case_id"],
        "measured_values": {"first_exhibition_frame": exhibition["first_exhibition_frame"],
                            "frame_count": len(events)},
        "target_checks": [{"target": "simultaneous_facing_dual_green",
                           "requested": requested, "measured": observed,
                           "method": "source-joined original lamp packet at first exhibition",
                           "tolerance": "exact aspects", "matched": sorted(observed) == sorted(requested),
                           "physical_cause_confirmed": False,
                           "cause_evidence": "Original pixel and official-head review pending"}],
        "setup_confirmed": False, "behavior_attempted": True,
        "maneuver_completed": bool(report["measurements"]["straight_movement_context"][
            "value"]["intersection_entry_observed"]),
        "termination_reason": "original planned frames exhausted",
        "physical_failure_flags": {"physical_dual_aspect_unverified": True},
        "trace_reference": "trace.jsonl", "video_references": list(VIDEOS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": evidence, "realized_observables": {},
    }
    path = root / "result.json"
    require(not path.exists(), "selected result already published")
    path.write_text(json.dumps(result, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    return result
