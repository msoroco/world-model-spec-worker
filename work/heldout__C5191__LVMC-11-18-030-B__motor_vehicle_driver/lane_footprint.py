"""Value-free footprint geometry for a recorded marked traffic lane.

The caller supplies native lane boundary vertices and measured vehicle corners
from the same frame. This module does not decide lawful lane use or exceptions.
"""

from __future__ import annotations

from math import hypot, isfinite


def _point(value):
    if len(value) != 2 or not all(isfinite(float(v)) for v in value):
        raise ValueError("Expected finite two-dimensional coordinates")
    return float(value[0]), float(value[1])


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _distance_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    norm = dx * dx + dy * dy
    if norm == 0:
        raise ValueError("Coincident boundary vertices")
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / norm))
    return hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _inside(p, polygon):
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < x:
                inside = not inside
    return inside


def _strict_intersection(a, b, c, d):
    return _cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0


def measure_footprint(lane_polygon, body_corners):
    """Return signed minimum corner clearance and full-body containment.

    Positive clearance means every measured body corner is inside. Zero means
    boundary contact. Negative means at least one corner is outside. Segment
    crossings are checked separately so a concave lane cannot hide an excursion.
    Values are physical distances in the coordinate system supplied by capture.
    """
    lane = [_point(v) for v in lane_polygon]
    body = [_point(v) for v in body_corners]
    if len(lane) < 3 or len(body) != 4:
        raise ValueError("Need a lane polygon and four vehicle body corners")
    lane_edges = list(zip(lane, lane[1:] + lane[:1]))
    body_edges = list(zip(body, body[1:] + body[:1]))
    if any(a == b for a, b in lane_edges + body_edges):
        raise ValueError("Degenerate geometry")
    signed = []
    for corner in body:
        distance = min(_distance_to_segment(corner, a, b) for a, b in lane_edges)
        signed.append(distance if _inside(corner, lane) else -distance)
    crosses = any(_strict_intersection(a, b, c, d) for a, b in body_edges for c, d in lane_edges)
    clearance = min(signed)
    return {
        "minimum_corner_clearance_m": clearance,
        "corner_clearances_m": signed,
        "boundary_crossing": crosses,
        "all_corners_inside": all(value > 0 for value in signed),
        "full_footprint_inside": all(value > 0 for value in signed) and not crosses,
    }
