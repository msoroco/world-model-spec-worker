"""Measure two-vehicle intersection entry without deciding legal priority.

The law says "approximately the same time" but supplies no numeric window.
This module reports the observed delta and preserves the roadway/device facts.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED = ("crossing_history.jsonl", "road_geometry.json", "video_frames.jsonl")


def _source(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _pair(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
        not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
        for v in value
    ):
        raise ValueError("Missing finite " + label)
    return value


def _body(actor):
    vertices = actor.get("body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing complete participant body")
    return MultiPoint([_pair(v, "body vertex") for v in vertices]).convex_hull


def _right_side(origin, heading_deg, other_origin):
    """Signed lateral projection onto the driver's right-hand axis."""
    theta = math.radians(heading_deg)
    dx, dy = other_origin[0] - origin[0], other_origin[1] - origin[1]
    right_m = dx * math.sin(theta) - dy * math.cos(theta)
    if abs(right_m) < 1.0:
        raise ValueError("Approach side is geometrically ambiguous")
    return right_m


def analyze(root: Path) -> dict:
    root = Path(root)
    paths, hashes = {}, {}
    for name in REQUIRED:
        paths[name], hashes[name] = _source(root, name)
    geometry = json.loads(paths["road_geometry.json"].read_text())
    polygon = geometry.get("intersection_polygon_xy_m")
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("Missing identified intersection polygon")
    intersection = Polygon([_pair(v, "intersection vertex") for v in polygon])
    if not intersection.is_valid or intersection.area <= 0:
        raise ValueError("Invalid identified intersection polygon")
    for key in ("intersection_id", "ego_highway_id", "other_highway_id",
                "device_inventory_source", "ego_approach_heading_deg",
                "other_approach_heading_deg", "approach_geometry_source"):
        if key not in geometry or geometry[key] in (None, ""):
            raise ValueError("Missing sourced road context: " + key)
    ego_origin = _pair(geometry.get("ego_approach_origin_xy_m"), "ego approach origin")
    other_origin = _pair(geometry.get("other_approach_origin_xy_m"), "other approach origin")
    for key in ("ego_approach_heading_deg", "other_approach_heading_deg"):
        if type(geometry[key]) not in (int, float) or not math.isfinite(geometry[key]):
            raise ValueError("Finite sourced approach heading required")
    ego_right = _right_side(ego_origin, geometry["ego_approach_heading_deg"], other_origin)
    other_right = _right_side(other_origin, geometry["other_approach_heading_deg"], ego_origin)
    if (ego_right > 0) == (other_right > 0):
        raise ValueError("Approach sides are not reciprocal")
    history, mapping = _rows(paths["crossing_history.jsonl"]), _rows(paths["video_frames.jsonl"])
    if len(history) < 2 or len(mapping) != len(history):
        raise ValueError("Incomplete source/frame map")
    previous = (-1, -math.inf)
    occupancy = {"ego": [], "other": []}
    for i, (row, frame) in enumerate(zip(history, mapping)):
        identity = (row.get("frame"), row.get("time_s"))
        if type(identity[0]) is not int or not isinstance(identity[1], (int, float)) or isinstance(identity[1], bool) or not math.isfinite(identity[1]) or identity[0] <= previous[0] or identity[1] <= previous[1]:
            raise ValueError("Nonmonotone original frame/time")
        previous = identity
        if frame.get("video_frame") != i or frame.get("carla_frame") != identity[0] or abs(frame.get("time_s", -math.inf) - identity[1]) > 1e-4:
            raise ValueError("Original frame/time join failed")
        for participant in ("ego", "other"):
            actor = row.get(participant)
            if not isinstance(actor, dict):
                raise ValueError("Missing participant: " + participant)
            _pair(actor.get("position_xy_m"), participant + " position")
            if _body(actor).intersects(intersection):
                occupancy[participant].append({"frame": identity[0], "time_s": identity[1]})
    first = {who: values[0] if values else None for who, values in occupancy.items()}
    difference = (first["ego"]["time_s"] - first["other"]["time_s"]
                  if all(first.values()) else None)
    heading_difference = ((geometry["other_approach_heading_deg"] -
                           geometry["ego_approach_heading_deg"] + 180) % 360 - 180)
    return {
        "format": "worker-crossing-entry-measurements",
        "sources": hashes,
        "intersection_id": geometry["intersection_id"],
        "highway_ids": [geometry["ego_highway_id"], geometry["other_highway_id"]],
        "device_inventory_source": geometry["device_inventory_source"],
        "first_body_entry": first,
        "ego_minus_other_entry_time_s": difference,
        "approach_heading_difference_deg": heading_difference,
        "approach_geometry_source": geometry["approach_geometry_source"],
        "other_lateral_to_ego_right_m": ego_right,
        "ego_lateral_to_other_right_m": other_right,
        "other_is_to_ego_right": ego_right > 0,
        "ego_is_to_other_right": other_right > 0,
        "geometric_yield_candidate": "ego" if ego_right > 0 else "other",
        "approximately_same_time_judgment": "unresolved; no numeric legal threshold",
        "right_of_way_judgment": "unresolved",
    }
