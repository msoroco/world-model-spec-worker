"""Project verified original arrow sources into pinned Native result channels."""
from __future__ import annotations

import json
from pathlib import Path


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def build_result(attempt, report):
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    planned = construction["recording_description"]
    site = json.loads((attempt / "site.json").read_text())
    events = json.loads((attempt / "arrow-events-original.json").read_text())
    aspects = json.loads((attempt / "arrow-aspect-original.json").read_text())
    mapping = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    if (not events or len(events) != len(aspects) or len(events) != len(mapping)
            or len(events) != len(trace)):
        raise ValueError("original arrow and Native frame histories differ")
    for index, (event, aspect, frame, motion) in enumerate(zip(events, aspects, mapping, trace)):
        if (event["frame"] != aspect["frame"] or
            aspect["frame"] != frame["carla_frame"] or
            frame["carla_frame"] != motion["frame"] or
            frame["video_frame"] != index or
            abs(frame["time_s"] - motion["time_s"]) > 1e-6):
            raise ValueError("original arrow and Native timestamp join differs")
    route = (site["concurrent_route_xy"] if
             config["case_suffix"] == "arrow_concurrent_movement" else site["ego_route_xy"])
    streams = {
        "ego_body_heading_history": [
            {"ego_xy": e["ego_xy"], "ego_z_m": e["ego_z_m"],
             "body_vertices_m": e["ego_body_vertices_m"],
             "speed_mps": e["ego_speed_mps"], "brake": e["ego_brake"],
             "heading_deg": e["ego_heading_deg"]} for e in events],
        "facing_arrow_history": aspects,
        "pedestrian_body_lawful_history": [
            [u for u in e["other_users"] if u["kind"] == "pedestrian"] for e in events],
        "other_traffic_history": [
            [u for u in e["other_users"] if u["kind"] == "motor_vehicle"] for e in events],
        "concurrent_indication_history": [a["concurrent_indications"] for a in aspects],
        "turn_route": [{"route_xy": route, "ego_movement": e["ego_movement"]} for e in events],
        "camera_frame_map": mapping,
    }
    context = {
        "intersection_context": {"polygon_xy": site["intersection_polygon_xy"],
                                 "native_map_name": site["native_map_name"]},
        "pedestrian_entry_context": {"source_refs": [u.get("lawful_presence_source")
                                       for e in events for u in e["other_users"]
                                       if u["kind"] == "pedestrian"],
                                     "adjacent_crosswalk_polygon_xy": site["adjacent_crosswalk_polygon_xy"]},
        "traffic_entry_context": {"source_refs": [u.get("lawful_presence_source")
                                    for e in events for u in e["other_users"]
                                    if u["kind"] == "motor_vehicle"]},
        "signal_controller_context": {"official_head_id": site["official_head_id"],
                                       "signal_source_path": site["signal_source_path"]},
        "route_source_context": {"route_xy": route,
                                 "route_source_path": site["route_source_path"]},
    }
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in planned["channels"]:
        name = channel["name"]
        if name not in streams:
            raise ValueError("unsupported exact arrow channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for frame, value in zip(mapping, streams[name]):
                stream.write(json.dumps({"time_s": frame["time_s"], "value": value},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_path = channels / "context.json"
    context_path.write_text(json.dumps(context, allow_nan=False) + "\n")
    for item in planned["context_inputs"]:
        if item["name"] not in context:
            raise ValueError("unsupported exact arrow context: " + item["name"])
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    result = {"case_id": config["selected_case_id"],
              "measured_values": {name: item["value"] for name, item in report["measurements"].items()},
              "target_checks": [{"target": "verified original arrow and four-camera join",
                                 "requested": True, "measured": True,
                                 "method": "saved source and frame identity verification",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": report["source_inventory"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved assessment pending independent physical review",
              "physical_failure_flags": [],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": planned, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result
