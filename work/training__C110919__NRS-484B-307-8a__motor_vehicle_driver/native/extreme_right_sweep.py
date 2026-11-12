"""Authored lateral route sweep and saved Native full-body measurements.

Positive offsets move toward the right edge of the surveyed approach lane.
The measurement reports geometry; it makes no legal extreme-right finding.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from geometry import LANE_WIDTH_M, route


@dataclass(frozen=True)
class LateralOffset:
    right_m: float

    def __post_init__(self):
        if type(self.right_m) not in (int, float) or not math.isfinite(self.right_m):
            raise ValueError("Lateral offset must be finite")
        if not 0 <= self.right_m <= .6:
            raise ValueError("Lateral offset outside declared physical probe range")

    def route(self):
        base = route()
        offset = self.right_m
        result = []
        for index, (x, y) in enumerate(base):
            if index <= 330:
                point = [x + offset, y]
            elif index <= 488:
                theta = math.pi - (index - 330) * (math.pi / 2) / 158
                radius = 5.25 - offset
                point = [7 + radius * math.cos(theta), -7 + radius * math.sin(theta)]
            else:
                point = [x, y - offset]
            result.append([round(value, 5) for value in point])
        if len(result) != len(base) or max(math.dist(a, b) for a, b in zip(result, result[1:])) > .11:
            raise ValueError("Shifted route continuity failed")
        return result


def approach_widths(native_lane_width_m, native_left_lane_width_m):
    values = (native_lane_width_m, native_left_lane_width_m)
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("Native approach/highway widths absent")
    return {"approach_lane_width_m": native_lane_width_m,
            "highway_width_m": sum(values),
            "authored_lane_width_m": LANE_WIDTH_M}


def measure_approach(samples, geometry):
    """Measure all four saved Native body corners against surveyed edge positions."""
    survey = geometry.get("approach_lateral_geometry", {})
    right = survey.get("right_edge_x_m")
    center = survey.get("lane_center_x_m")
    width = survey.get("lane_width_m")
    highway_width = survey.get("highway_width_m")
    if any(type(v) not in (int, float) or not math.isfinite(v)
           for v in (right, center, width, highway_width)) or \
            width <= 0 or highway_width < width or abs((right - center) - width / 2) > .05:
        raise ValueError("Surveyed Native approach lane/highway edges absent")
    left = right - width
    highway_left = right - highway_width
    measured = []
    for index, row in enumerate(samples):
        body = row.get("native_body_xy_m")
        if not isinstance(body, list) or len(body) != 4 or any(
            not isinstance(p, list) or len(p) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in p)
            for p in body):
            raise ValueError("Original Native full body absent")
        if row.get("native_frame") is None:
            raise ValueError("Original Native frame identity absent")
        # Road 1 is the south approach. Ignore turn/receiving-road rows here;
        # the runner retains their own per-frame Native lane readback.
        lane = row.get("native_lane_geometry")
        if not isinstance(lane, dict) or lane.get("road_id") != 1:
            continue
        if lane.get("lane_id") != -1 or \
                abs(lane.get("lane_width_m", float("nan")) - width) > .05:
            raise ValueError("Approach Native lane readback differs")
        xs = [p[0] for p in body]
        measured.append({"index": index, "native_frame": row["native_frame"],
                         "rightmost_body_x_m": max(xs),
                         "leftmost_body_x_m": min(xs),
                         "right_edge_clearance_m": right - max(xs),
                         "left_lane_clearance_m": min(xs) - left,
                         "highway_left_clearance_m": min(xs) - highway_left})
    if not measured:
        raise ValueError("No measured approach full-body frames")
    return {"approach_frames": len(measured),
            "surveyed_lane_width_m": width,
            "surveyed_highway_width_m": highway_width,
            "right_edge_x_m": right,
            "minimum_right_edge_clearance_m": min(r["right_edge_clearance_m"] for r in measured),
            "maximum_right_edge_clearance_m": max(r["right_edge_clearance_m"] for r in measured),
            "minimum_left_lane_clearance_m": min(r["left_lane_clearance_m"] for r in measured),
            "first": measured[0], "last": measured[-1],
            "source": "saved_native_full_body_and_lane_readback",
            "legal_extreme_right_verdict": None}
