"""Measure signal Yellow->Red onset against first body entry at C158196.

This reports observed ordering at original frames. It does not infer yellow
stopping feasibility or replace physical visibility review of the signal head.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED = ("signal_vehicle_history.jsonl", "video_frames.jsonl", "junction_context.json")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite geometry/time value")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _polygon(context):
    vertices = context.get("intersection_polygon_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError("Missing sourced intersection polygon")
    polygon = Polygon([(_number(v[0]), _number(v[1])) for v in vertices])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid intersection polygon")
    return polygon


def _inside(row, polygon):
    vertices = row.get("ego_body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing complete ego body vertices")
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
    for key in ("native_map_id", "intersection_id", "native_signal_id", "governed_road_id",
                "governed_lane_id", "signal_head_video_source", "lane_governance_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced signal/junction context: " + key)
    polygon = _polygon(context)
    rows, frames = _rows(root / "signal_vehicle_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete signal/vehicle/frame history")
    previous = (-1, -math.inf)
    observed, first_entry, red_onset = [], None, None
    prior_inside, prior_state = None, None
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if row.get("native_signal_id") != context["native_signal_id"] or row.get("road_id") != context["governed_road_id"] or row.get("lane_id") != context["governed_lane_id"]:
            raise ValueError("Signal or approach governance identity mismatch")
        state = row.get("signal_state")
        if state not in ("Green", "Yellow", "Red"):
            raise ValueError("Invalid signal state for this branch")
        inside = _inside(row, polygon)
        if index == 0 and inside:
            raise ValueError("No pre-entry approach observation")
        event = {"frame": fid, "time_s": time}
        if prior_state == "Yellow" and state == "Red" and red_onset is None:
            red_onset = event
        if prior_inside is False and inside and first_entry is None:
            first_entry = event | {"signal_state": state}
        observed.append({"frame": fid, "time_s": time, "signal_state": state,
                         "ego_speed_mps": _number(row.get("ego_speed_mps")), "body_in_intersection": inside})
        prior_state, prior_inside = state, inside
    if red_onset is None:
        raise ValueError("No observed Yellow-to-Red transition")
    if first_entry is None:
        raise ValueError("No observed ego body entry")
    return {"format": "worker-yellow-red-body-entry-observations", "sources": sources,
            "intersection_id": context["intersection_id"],
            "yellow_to_red_onset": red_onset, "first_body_entry": first_entry,
            "entry_minus_red_onset_s": first_entry["time_s"] - red_onset["time_s"],
            "entry_with_red_exhibited_observed": first_entry["signal_state"] == "Red",
            "samples": observed,
            "yellow_stop_feasibility_judgment": "unresolved",
            "physical_head_visibility_judgment": "unresolved"}
