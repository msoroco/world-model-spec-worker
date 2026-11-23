"""Measured Native body footprint relative to a reviewed parking polygon.

The polygon must be derived from inspected map geometry. The caller retains its
map/source hash and original frame; this function does not create an intersection.
"""
from __future__ import annotations

import math


def _point_inside(point, polygon):
    x, y = point
    inside = False
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if abs(cross) < 1e-9 and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9:
            return True
        if (y1 > y) != (y2 > y):
            if x < x1 + (x2 - x1) * (y - y1) / (y2 - y1):
                inside = not inside
    return inside


def classify_footprint(body_corners_xy_m, reviewed_parking_polygon_xy_m,
                       reviewed_intersection_polygon_xy_m):
    """Return full-footprint containment and physical intersection overlap.

    All inputs are actual Native world XY coordinates. A body corner inside the
    intersection polygon is a conservative overlap witness; false means no
    corner witness, not proof the polygons are disjoint.
    """
    body = body_corners_xy_m
    parking = reviewed_parking_polygon_xy_m
    intersection = reviewed_intersection_polygon_xy_m
    if len(body) != 4 or len(parking) < 3 or len(intersection) < 3:
        raise ValueError("four body corners and reviewed polygons required")
    for point in (*body, *parking, *intersection):
        if len(point) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in point):
            raise ValueError("invalid original world XY")
    return {"footprint_inside_reviewed_parking_polygon": all(_point_inside(p, parking) for p in body),
            "body_corner_inside_intersection_count": sum(_point_inside(p, intersection) for p in body),
            "intersection_overlap_method": "body_corner_witness_only"}
