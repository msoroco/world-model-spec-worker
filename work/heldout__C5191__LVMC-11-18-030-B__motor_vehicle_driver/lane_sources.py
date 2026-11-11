"""Original-tick marked-lane and participant source for C147331.

This module records geometry and Native readbacks. It does not classify lawful
passing or turning, and is safe to import without CARLA installed.
"""

from __future__ import annotations

import json
from math import atan2, isfinite
from pathlib import Path


def _xy(point):
    pair = (float(point.x), float(point.y))
    if not all(isfinite(value) for value in pair):
        raise ValueError("Nonfinite Native coordinate")
    return pair


def body_corners(actor):
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8:
        raise ValueError("Native actor needs eight bounding-box vertices")
    if any(not isfinite(float(vertex.z)) for vertex in vertices):
        raise ValueError("Nonfinite Native body height")
    lower = sorted(vertices, key=lambda vertex: float(vertex.z))[:4]
    points = [_xy(point) for point in lower]
    if len(set(points)) != 4:
        raise ValueError("Degenerate Native body footprint")
    center = (sum(p[0] for p in points) / 4, sum(p[1] for p in points) / 4)
    points.sort(key=lambda p: atan2(p[1] - center[1], p[0] - center[0]))
    return [list(point) for point in points]


def marked_lane_slice(waypoint, *, half_length_m=2.0):
    """Sample a local lane rectangle from a Native waypoint and its markings.

    The rectangle is a local measurement slice, not an invented entire-lane
    polygon. Capture must supply a waypoint for each original ego tick.
    """
    if not (isfinite(half_length_m) and half_length_m > 0):
        raise ValueError("Invalid local lane sampling length")
    width = float(waypoint.lane_width)
    if not (isfinite(width) and width > 0):
        raise ValueError("Invalid Native lane width")
    left_marking = getattr(waypoint, "left_lane_marking", None)
    right_marking = getattr(waypoint, "right_lane_marking", None)
    if left_marking is None or right_marking is None:
        raise ValueError("Native lane markings missing")
    left_type = str(left_marking.type)
    right_type = str(right_marking.type)
    if any(value.rsplit(".", 1)[-1].lower() == "none"
           for value in (left_type, right_type)):
        raise ValueError("Unmarked lane boundary")
    transform = waypoint.transform
    center = _xy(transform.location)
    forward = _xy(transform.get_forward_vector())
    norm = (forward[0] ** 2 + forward[1] ** 2) ** 0.5
    if norm <= 0:
        raise ValueError("Invalid Native waypoint heading")
    fx, fy = forward[0] / norm, forward[1] / norm
    lx, ly = -fy, fx
    polygon = []
    for along, across in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        polygon.append([center[0] + along * half_length_m * fx + across * width / 2 * lx,
                        center[1] + along * half_length_m * fy + across * width / 2 * ly])
    return {"polygon_xy_m": polygon, "lane_id": int(waypoint.lane_id),
            "road_id": int(waypoint.road_id), "lane_width_m": width,
            "left_marking": left_type, "right_marking": right_type,
            "lane_heading_xy": [fx, fy]}


class LaneSourceRecorder:
    """Write synchronized raw observations, one row per original Native tick."""

    def __init__(self, directory, ego, *, overtaken=None):
        if ego.id is None or overtaken is not None and (
                overtaken.id is None or overtaken.id == ego.id):
            raise ValueError("Distinct Native participant IDs required")
        self.ego, self.overtaken = ego, overtaken
        self.path = Path(directory) / "marked_lane_sources.jsonl"
        self.stream = self.path.open("x", encoding="utf-8")
        self.previous = None

    def append(self, frame, time_s, waypoint):
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError("Invalid Native frame or time")
        if self.previous is not None and (
                frame != self.previous[0] + 1 or time_s <= self.previous[1]):
            raise ValueError("Missing or unordered Native lane frame")
        lane = marked_lane_slice(waypoint)
        velocity = _xy(self.ego.get_velocity())
        row = {"frame": frame, "time_s": time_s,
               "ego_id": int(self.ego.id), "ego_corners_xy_m": body_corners(self.ego),
               "ego_velocity_xy_mps": list(velocity), "lane": lane,
               "ego_light_state": str(self.ego.get_light_state()) if hasattr(self.ego, "get_light_state") else None,
               "overtaken_id": None, "overtaken_corners_xy_m": None,
               "overtaken_velocity_xy_mps": None}
        if self.overtaken is not None:
            row["overtaken_id"] = int(self.overtaken.id)
            row["overtaken_corners_xy_m"] = body_corners(self.overtaken)
            row["overtaken_velocity_xy_mps"] = list(_xy(self.overtaken.get_velocity()))
        self.stream.write(json.dumps(row, allow_nan=False) + "\n")
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
