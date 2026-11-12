"""Retain original two-way road and full-body geometry for right-half analysis.

The caller supplies the selected Native waypoint each tick. This baseline
acquisition only supports a directly adjacent opposite-direction driving lane;
other road arrangements require their own audited map geometry.
"""

import json
from math import atan2, hypot, isfinite
from pathlib import Path


def _xy(location):
    values = (float(location.x), float(location.y))
    if not all(isfinite(value) for value in values):
        raise ValueError("Nonfinite Native road or body geometry")
    return values


def _forward(waypoint):
    vector = waypoint.transform.get_forward_vector()
    x, y = _xy(vector)
    length = hypot(x, y)
    if length < 1e-6:
        raise ValueError("Degenerate Native road tangent")
    return x / length, y / length


def _opposing_neighbor(waypoint):
    tangent = _forward(waypoint)
    options = [waypoint.get_left_lane(), waypoint.get_right_lane()]
    matches = []
    for candidate in options:
        if candidate is None or candidate.road_id != waypoint.road_id:
            continue
        if str(candidate.lane_type).split(".")[-1] != "Driving":
            continue
        other = _forward(candidate)
        if tangent[0] * other[0] + tangent[1] * other[1] < -0.8:
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError("Two-way baseline needs exactly one adjacent opposing driving lane")
    return matches[0]


def sample_two_way_baseline(actor, waypoint, frame, time_s):
    """Sample one original 20 Hz frame, without deciding any legal exception."""
    if type(frame) is not int or frame < 0 or not isfinite(float(time_s)):
        raise ValueError("Invalid Native frame/time")
    other = _opposing_neighbor(waypoint)
    own_center = _xy(waypoint.transform.location)
    other_center = _xy(other.transform.location)
    tangent = _forward(waypoint)
    lateral_gap = abs(tangent[0] * (other_center[1] - own_center[1]) -
                      tangent[1] * (other_center[0] - own_center[0]))
    own_width, other_width = float(waypoint.lane_width), float(other.lane_width)
    if min(own_width, other_width) <= 0 or not all(
            isfinite(value) for value in (own_width, other_width, lateral_gap)):
        raise ValueError("Invalid Native driving lane width")
    if abs(lateral_gap - (own_width + other_width) / 2) > 0.5:
        raise ValueError("Adjacent lane centers do not support the declared centerline")
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) != 8:
        raise ValueError("Native vehicle bounding box needs eight vertices")
    points = [_xy(vertex) for vertex in vertices]
    footprint = sorted({point for point in points})
    if len(footprint) != 4:
        raise ValueError("Native vehicle footprint needs four distinct corners")
    cx = sum(point[0] for point in footprint) / 4
    cy = sum(point[1] for point in footprint) / 4
    footprint.sort(key=lambda point: atan2(point[1] - cy, point[0] - cx))
    return {"frame": frame, "time_s": float(time_s),
            "road_id": waypoint.road_id, "lane_id": waypoint.lane_id,
            "road_center_xy": [(own_center[0] + other_center[0]) / 2,
                               (own_center[1] + other_center[1]) / 2],
            "road_travel_tangent_xy": list(tangent),
            "road_width_m": own_width + other_width,
            "ego_corners_xy": [list(point) for point in footprint],
            "source_kind": "Native original waypoint and actor body readback",
            "legal_width_or_exception_decided": False}


class RoadSourceRecorder:
    """Write sequential original samples without replacing an earlier attempt."""

    def __init__(self, output_dir):
        self.path = Path(output_dir) / "ego_road_frames.jsonl"
        self.stream = self.path.open("x", encoding="utf-8")
        self.previous = None

    def append(self, actor, waypoint, frame, time_s):
        if self.stream.closed:
            raise ValueError("Original road source recorder is closed")
        if self.previous is not None and (frame != self.previous[0] + 1 or
                                          abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError("Original road samples must be consecutive at 20 Hz")
        row = sample_two_way_baseline(actor, waypoint, frame, time_s)
        self.stream.write(json.dumps(row, separators=(",", ":")) + "\n")
        self.previous = frame, time_s
        return row

    def close(self):
        if not self.stream.closed:
            self.stream.close()
