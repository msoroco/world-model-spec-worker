"""Original-frame geometry for the one-way roadway parking probes.

This module measures physical facts. It does not choose a legal parallelism
threshold, determine whether a halt is standing or parking, or resolve a
Chapter exception.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def vector(start, end):
    return (float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))


def unit(value):
    if len(value) != 2 or not all(math.isfinite(float(item)) for item in value):
        raise ValueError("finite XY vector required")
    norm = math.hypot(float(value[0]), float(value[1]))
    if norm <= 0:
        raise ValueError("nonzero XY vector required")
    return (float(value[0]) / norm, float(value[1]) / norm)


def closest_segment(point, polyline):
    if len(polyline) < 2:
        raise ValueError("road edge needs two or more source vertices")
    nearest = None
    for start, end in zip(polyline, polyline[1:]):
        tangent = vector(start, end)
        length2 = sum(value * value for value in tangent)
        if length2 <= 0:
            raise ValueError("road edge has a zero-length segment")
        projection = sum((point[i] - float(start[i])) * tangent[i] for i in (0, 1)) / length2
        projection = min(1.0, max(0.0, projection))
        foot = tuple(float(start[i]) + projection * tangent[i] for i in (0, 1))
        distance = math.dist(point, foot)
        candidate = (distance, unit(tangent), foot)
        if nearest is None or candidate[0] < nearest[0]:
            nearest = candidate
    return nearest


def inside(point, polygon):
    if len(polygon) < 3:
        raise ValueError("roadway needs a source polygon")
    x, y = (float(value) for value in point)
    hits = False
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay = (float(value) for value in start)
        bx, by = (float(value) for value in end)
        if (ay > y) != (by > y):
            crossing = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < crossing:
                hits = not hits
    return hits


def measure_frame(frame, context):
    body = frame["body_vertices_xy_m"]
    if len(body) != 4 or any(len(point) != 2 for point in body):
        raise ValueError("original body needs four XY corners")
    flat = [float(value) for point in body for value in point]
    if not all(math.isfinite(value) for value in flat):
        raise ValueError("original body coordinates must be finite")
    center = (sum(point[0] for point in body) / 4,
              sum(point[1] for point in body) / 4)
    heading = unit(frame["vehicle_forward_xy"])
    distance, edge, foot = closest_segment(center, context["road_edge_xy_m"])
    lawful = unit(context["lawful_travel_xy"])
    if abs(sum(edge[i] * lawful[i] for i in (0, 1))) < .9:
        raise ValueError("authored edge and lawful direction are inconsistent")
    edge_alignment = abs(sum(heading[i] * edge[i] for i in (0, 1)))
    lawful_alignment = sum(heading[i] * lawful[i] for i in (0, 1))
    return {"frame": frame["frame"], "time_s": frame["time_s"],
            "body_center_xy_m": center, "nearest_edge_xy_m": foot,
            "center_edge_distance_m": distance,
            "parallel_deviation_deg": math.degrees(math.acos(min(1.0, edge_alignment))),
            "lawful_heading_deviation_deg": math.degrees(math.acos(max(-1.0, min(1.0, lawful_alignment)))),
            "heading_lawful_dot": lawful_alignment,
            "body_corners_inside_roadway": sum(inside(point, context["roadway_polygon_xy_m"])
                                               for point in body),
            "engineering_measurement_only": True}


def measure_sequence(frames, context):
    if not frames:
        raise ValueError("original body history is empty")
    numbers = [frame["frame"] for frame in frames]
    times = [frame["time_s"] for frame in frames]
    if (any(type(number) is not int for number in numbers) or
            any(b <= a for a, b in zip(numbers, numbers[1:])) or
            any(type(value) not in (int, float) or not math.isfinite(value) for value in times) or
            any(b <= a for a, b in zip(times, times[1:]))):
        raise ValueError("original frame/time order invalid")
    return {"frames": [measure_frame(frame, context) for frame in frames],
            "lawful_direction_source": context["lawful_direction_source"],
            "road_edge_source": context["road_edge_source"],
            "roadway_source": context["roadway_source"],
            "legal_judgment": "unresolved"}


def load_original(path, expected_sha256, context):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("original parking body source hash changed")
    frames = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    return measure_sequence(frames, context)
