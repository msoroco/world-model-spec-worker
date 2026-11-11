"""Measure original marked-lane rows; no geometric or legal tolerance is added."""

from __future__ import annotations

import json
from pathlib import Path

from lane_footprint import measure_footprint


def _center(corners):
    if len(corners) != 4:
        raise ValueError("Native participant body corners missing")
    return (sum(float(point[0]) for point in corners) / 4,
            sum(float(point[1]) for point in corners) / 4)


def measure_saved_sources(source_path, *, expected_ego_id, require_overtaken=False):
    path = Path(source_path)
    if not path.is_file():
        raise ValueError("Original marked-lane source missing")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("Original marked-lane source empty")
    result = []
    prior = None
    participant_id = None
    for line in lines:
        row = json.loads(line)
        frame, time_s = row["frame"], row["time_s"]
        if type(frame) is not int or type(time_s) not in (int, float):
            raise ValueError("Invalid original frame identity")
        if prior is not None and (frame != prior[0] + 1 or time_s <= prior[1]):
            raise ValueError("Missing or unordered original lane frame")
        if row["ego_id"] != expected_ego_id:
            raise ValueError("Ego Native identity changed")
        if require_overtaken and row.get("overtaken_id") is None:
            raise ValueError("Passing participant source missing")
        if participant_id is None:
            participant_id = row.get("overtaken_id")
        elif row.get("overtaken_id") != participant_id:
            raise ValueError("Passing participant Native identity changed")
        lane = row["lane"]
        if not lane.get("left_marking") or not lane.get("right_marking"):
            raise ValueError("Native lane marking source missing")
        measured = measure_footprint(lane["polygon_xy_m"], row["ego_corners_xy_m"])
        longitudinal_gap = None
        if row.get("overtaken_id") is not None:
            heading = lane["lane_heading_xy"]
            if len(heading) != 2:
                raise ValueError("Native lane heading missing")
            ego_center = _center(row["ego_corners_xy_m"])
            other_center = _center(row["overtaken_corners_xy_m"])
            longitudinal_gap = sum((ego_center[i] - other_center[i]) * float(heading[i])
                                   for i in range(2))
        result.append({"frame": frame, "time_s": time_s,
                       "road_id": lane["road_id"], "lane_id": lane["lane_id"],
                       "left_marking": lane["left_marking"],
                       "right_marking": lane["right_marking"],
                       "overtaken_id": row.get("overtaken_id"),
                       "ego_light_state": row.get("ego_light_state"),
                       "ego_minus_other_longitudinal_m": longitudinal_gap,
                       "minimum_corner_clearance_m": measured["minimum_corner_clearance_m"],
                       "boundary_crossing": measured["boundary_crossing"],
                       "full_footprint_inside": measured["full_footprint_inside"]})
        prior = frame, time_s
    gaps = [frame["ego_minus_other_longitudinal_m"] for frame in result
            if frame["ego_minus_other_longitudinal_m"] is not None]
    behind_seen = False
    order_reversal = False
    for gap in gaps:
        if gap < 0:
            behind_seen = True
        elif gap > 0 and behind_seen:
            order_reversal = True
    return {"source": str(path), "ego_id": expected_ego_id,
            "overtaken_id": participant_id, "frames": result,
            "measured_order_reversal": order_reversal}
