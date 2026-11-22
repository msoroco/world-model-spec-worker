"""Measure other-first entry at a yield-sign-controlled median opening.

This preserves Native junction/highway identity, sign-governed approach and
source frames. Entry order is observed even when the official-device exclusion
may make NRS 484B.250(1) inapplicable; no legal verdict is produced.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED = ("crossing_history.jsonl", "video_frames.jsonl", "junction_context.json")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite Native observation")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _inside(actor, polygon):
    vertices = actor.get("body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing complete actor body")
    body = MultiPoint([(_number(v[0]), _number(v[1])) for v in vertices]).convex_hull
    return body.intersects(polygon)


def analyze(root: Path) -> dict:
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "junction_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "ego_highway_id", "other_highway_id",
                "ego_road_id", "other_road_id", "native_yield_sign_id", "sign_governance_source",
                "yield_sign_video_source", "intersection_polygon_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced crossing context: " + key)
    if context["ego_highway_id"] == context["other_highway_id"]:
        raise ValueError("Approaches must be from different highways")
    if context.get("yield_sign_erected") is not True or context.get("yield_sign_governed_road_id") != context["ego_road_id"]:
        raise ValueError("Properly erected governing yield sign not sourced")
    vertices = context.get("intersection_polygon_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError("Missing sourced intersection polygon")
    polygon = Polygon([(_number(v[0]), _number(v[1])) for v in vertices])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid intersection polygon")
    rows, frames = _rows(root / "crossing_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete crossing/frame history")
    prior = (-1, -math.inf)
    first_entry = {"ego": None, "other": None}
    prior_inside = {"ego": False, "other": False}
    samples = []
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original frame/time")
        if index and fid != prior[0] + 1:
            raise ValueError("Missing original frame in crossing history")
        prior = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if row.get("native_yield_sign_id") != context["native_yield_sign_id"]:
            raise ValueError("Identified governing yield sign not observed")
        sample = {"frame": fid, "time_s": time}
        for who in ("ego", "other"):
            actor = row.get(who)
            if not isinstance(actor, dict) or actor.get("intersection_id") != context["intersection_id"] or actor.get("road_id") != context[who + "_road_id"]:
                raise ValueError("Actor not on sourced junction approach")
            inside = _inside(actor, polygon)
            if index == 0 and inside:
                raise ValueError("No observed pre-entry approach")
            distance = _number(actor.get("distance_to_intersection_m"))
            speed = _number(actor.get("speed_mps"))
            if distance < 0 or speed < 0:
                raise ValueError("Invalid approach distance or speed")
            if inside and not prior_inside[who] and first_entry[who] is None:
                first_entry[who] = {"frame": fid, "time_s": time}
            prior_inside[who] = inside
            sample[who] = {"body_in_intersection": inside, "distance_to_intersection_m": distance,
                           "speed_mps": speed}
        samples.append(sample)
    if first_entry["other"] is None or first_entry["ego"] is None:
        raise ValueError("Both body entries must be observed")
    other_frame = first_entry["other"]["frame"]
    other_index = next(i for i, sample in enumerate(samples) if sample["frame"] == other_frame)
    ego_approaching_at_other_entry = (not samples[other_index]["ego"]["body_in_intersection"]
        and samples[other_index]["ego"]["distance_to_intersection_m"] > 0
        and other_index + 1 < len(samples)
        and samples[other_index + 1]["ego"]["distance_to_intersection_m"] < samples[other_index]["ego"]["distance_to_intersection_m"])
    ego_speeds_while_other_inside = [sample["ego"]["speed_mps"] for sample in samples
                                     if sample["other"]["body_in_intersection"] and not sample["ego"]["body_in_intersection"]]
    return {"format": "worker-yield-sign-other-first-observations", "sources": sources,
            "intersection_id": context["intersection_id"],
            "highway_ids": [context["ego_highway_id"], context["other_highway_id"]],
            "first_body_entry": first_entry,
            "other_entered_before_ego_observed": first_entry["other"]["time_s"] < first_entry["ego"]["time_s"],
            "ego_approaching_at_other_entry_observed": ego_approaching_at_other_entry,
            "minimum_ego_speed_while_other_inside_mps": min(ego_speeds_while_other_inside) if ego_speeds_while_other_inside else None,
            "samples": samples,
            "statutory_roadway_crossing_judgment": "unresolved",
            "official_device_exclusion_judgment": "unresolved; Native yield-sign trigger and images need authority review",
            "right_of_way_judgment": "unresolved"}


def finalize(root: Path, output: Path) -> dict:
    """Write a source-hashed diagnostic from retained raw crossing sources."""
    report = analyze(root)
    report["source_kind"] = "original_frame_source_only"
    report["physical_acceptance_claimed"] = False
    report["legal_acceptance_claimed"] = False
    Path(output).write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    return report


def source_crossing_identity(context):
    return {key: context[key] for key in
            ("native_map_id", "intersection_id", "ego_highway_id", "other_highway_id")}


def complete_body_first_entry(report):
    return report["first_body_entry"]


def original_conflict_brake_frames(frames):
    return {"conflict_brake_frames": frames, "legal_yield_judgment": "unresolved"}


def native_yield_sign_identity(context):
    return {"native_yield_sign_id": context["native_yield_sign_id"],
            "official_device_exclusion_judgment": "unresolved"}


def original_body_occupancy_approach_frames(frames):
    return {"frames": frames, "count": len(frames)}


def runtime_finalize(attempt: Path, output: Path) -> dict:
    """Finalize a retained Native attempt through the pinned result protocol."""
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    assignment = "testing__C125763__NRS-484B-250-1__motor_vehicle_driver"
    case = assignment + "__yield_sign_other_inside"
    required = ("config.json", "junction_context.json", "crossing_history.jsonl",
                "controller_history.jsonl", "video_frames.jsonl", "trace.jsonl",
                "capture/evidence.jsonl", *(name + ".mkv" for name in
                  ("overview", "approach", "reference_corner", "driver_reference")))
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Use a fresh saved attempt and output")
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    if (config.get("assignment_id") != assignment or
            config.get("selected_case_id") != case or
            config.get("law_id") != "NRS-484B-250-1" or
            config.get("cell_id") != "C125763" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("frames") != 900 or config.get("rate_hz") != 20 or
            not isinstance(config.get("recording_description"), dict)):
        raise ValueError("Exact C125763(1) saved case configuration required")
    report = analyze(attempt)
    if len(report["samples"]) != 900:
        raise ValueError("Incomplete 900-frame original crossing history")
    if not report["other_entered_before_ego_observed"]:
        raise ValueError("Original other-first entry order missing")
    occupied_approach_frames = [row["frame"] for row in report["samples"]
        if row["other"]["body_in_intersection"] and
           not row["ego"]["body_in_intersection"] and
           0 < row["ego"]["distance_to_intersection_m"] <= 30]
    if len(occupied_approach_frames) < 10:
        raise ValueError("Other occupancy at ego approach absent")
    context = json.loads((attempt / "junction_context.json").read_text())
    if context.get("physical_acceptance_claimed") is not False:
        raise ValueError("Original context cannot claim physical acceptance")
    controls = _rows(attempt / "controller_history.jsonl")
    if len(controls) != len(report["samples"]):
        raise ValueError("Controller history does not cover original frames")
    conflict_frames = []
    for row, sample in zip(controls, report["samples"]):
        if row.get("frame") != sample["frame"] or row.get("time_s") != sample["time_s"]:
            raise ValueError("Original controller frame join failed")
        if type(row.get("other_conflict_clear")) is not bool:
            raise ValueError("Original controller conflict observation missing")
        command = row.get("commands", {}).get("ego", {})
        brake = command.get("brake")
        if type(brake) not in (int, float) or not math.isfinite(brake) or not 0 <= brake <= 1:
            raise ValueError("Original ego brake command missing")
        if (sample["other"]["body_in_intersection"] and
                not sample["ego"]["body_in_intersection"] and brake > 0):
            conflict_frames.append(row["frame"])
    sources = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
               for name in required}
    measurements = {
        "crossing_identity": {"method": "source_crossing_identity",
            "value": source_crossing_identity(context),
            "sources": {"junction_context.json": sources["junction_context.json"]}},
        "entry_order": {"method": "complete_body_first_entry",
            "value": complete_body_first_entry(report),
            "sources": {name: sources[name] for name in
                        ("crossing_history.jsonl", "video_frames.jsonl", "junction_context.json")}},
        "yield_observation": {"method": "original_conflict_brake_frames",
            "value": original_conflict_brake_frames(conflict_frames),
            "sources": {name: sources[name] for name in
                        ("controller_history.jsonl", "crossing_history.jsonl", "video_frames.jsonl")}},
        "other_occupancy_at_ego_approach": {"method": "original_body_occupancy_approach_frames",
            "value": original_body_occupancy_approach_frames(occupied_approach_frames),
            "sources": {name: sources[name] for name in
                        ("crossing_history.jsonl", "video_frames.jsonl", "junction_context.json")}},
        "device_qualification": {"method": "native_yield_sign_identity",
            "value": native_yield_sign_identity(context),
            "sources": {name: sources[name] for name in
                        ("junction_context.json", "crossing_history.jsonl")}},
    }
    channels = attempt / "channels"
    channels.mkdir()
    (channels / "entry_context.json").write_text(json.dumps(
        {"entry_context": {"case_id": case, "measurements": measurements,
                           "legal_conclusion": "unresolved"}}, allow_nan=False) + "\n")
    (channels / "entry_timing.jsonl").write_text("".join(json.dumps(
        {"time_s": row["time_s"], "value": {"frame": row["frame"],
         "ego_body_in_crossing": row["ego"]["body_in_intersection"],
         "other_body_in_crossing": row["other"]["body_in_intersection"]}},
        allow_nan=False) + "\n" for row in report["samples"]))
    stream_values = {
        "ego_speed": lambda row: row["ego"]["speed_mps"],
        "other_speed": lambda row: row["other"]["speed_mps"],
        "ego_approach_distance": lambda row: row["ego"]["distance_to_intersection_m"],
        "other_approach_distance": lambda row: row["other"]["distance_to_intersection_m"],
        "ego_body_inside": lambda row: row["ego"]["body_in_intersection"],
        "other_body_inside": lambda row: row["other"]["body_in_intersection"],
        "yield_sign_id": lambda row: context["native_yield_sign_id"],
    }
    for name, selector in stream_values.items():
        (channels / (name + ".jsonl")).write_text("".join(
            json.dumps({"time_s": row["time_s"], "value": selector(row)},
                       allow_nan=False) + "\n" for row in report["samples"]))
    result = {"case_id": case,
        "measured_values": {"other_entered_before_ego_observed": True,
                            "conflict_brake_frame_count": len(conflict_frames),
                            "other_occupied_ego_approach_frame_count": len(occupied_approach_frames)},
        "target_checks": [{"target": "other_body_enters_same_crossing_before_ego",
            "requested": True, "measured": True,
            "method": "original complete-body polygon and frame join", "tolerance": 0,
            "matched": True, "physical_cause_confirmed": False,
            "cause_evidence": ["junction_context.json", "crossing_history.jsonl",
                               "video_frames.jsonl"]},
            {"target": "other_body_occupies_crossing_during_ego_approach",
             "requested": True, "measured": True, "method": "original body polygons and joined frames",
             "tolerance": 0, "matched": True, "physical_cause_confirmed": False,
             "cause_evidence": ["crossing_history.jsonl", "video_frames.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved source analysis; Native and legal review pending",
        "physical_failure_flags": ["Official sign and statutory crossing judgments unresolved"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in
                             ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [
            {"name": item["name"], "unit": item["unit"],
             "reference": "channels/" + item["name"] + ".jsonl"}
            for item in config["recording_description"]["channels"]] + [
            {"name": "entry_context", "unit": "structured record",
             "reference": "channels/entry_context.json"}],
        "source_evidence_hashes": sources,
        "capture_evidence_sha256": sources["capture/evidence.jsonl"],
        "realized_observables": {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    output.write_text(json.dumps({"format": "worker-c125763-other-first-saved-analysis",
        "case_id": case, "measurements": measurements,
        "physical_acceptance_claimed": False,
        "legal_acceptance_claimed": False}, allow_nan=False, indent=2) + "\n")
    return measurements


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path, nargs="?")
    parser.add_argument("positional_output", type=Path, nargs="?")
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.attempt and args.output:
        runtime_finalize(args.attempt, args.output)
    elif args.source_dir and args.positional_output:
        finalize(args.source_dir, args.positional_output)
    else:
        parser.error("provide source_dir output or --attempt and --output")
