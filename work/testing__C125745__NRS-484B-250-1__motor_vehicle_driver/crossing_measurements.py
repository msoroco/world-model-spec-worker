"""Measure other-first entry at a stop-sign-controlled median opening.

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
                "ego_road_id", "other_road_id", "native_stop_sign_id", "sign_governance_source",
                "stop_sign_video_source", "intersection_polygon_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced crossing context: " + key)
    if context["ego_highway_id"] == context["other_highway_id"]:
        raise ValueError("Approaches must be from different highways")
    if context.get("stop_sign_erected") is not True or context.get("stop_sign_governed_road_id") != context["ego_road_id"]:
        raise ValueError("Properly erected governing stop sign not sourced")
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
        prior = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if row.get("native_stop_sign_id") != context["native_stop_sign_id"]:
            raise ValueError("Identified governing stop sign not observed")
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
    return {"format": "worker-stop-sign-other-first-observations", "sources": sources,
            "intersection_id": context["intersection_id"],
            "highway_ids": [context["ego_highway_id"], context["other_highway_id"]],
            "first_body_entry": first_entry,
            "other_entered_before_ego_observed": first_entry["other"]["time_s"] < first_entry["ego"]["time_s"],
            "ego_approaching_at_other_entry_observed": ego_approaching_at_other_entry,
            "minimum_ego_speed_while_other_inside_mps": min(ego_speeds_while_other_inside) if ego_speeds_while_other_inside else None,
            "samples": samples,
            "statutory_roadway_crossing_judgment": "unresolved",
            "official_device_exclusion_judgment": "unresolved; Native stop-sign trigger and images need authority review",
            "right_of_way_judgment": "unresolved"}
