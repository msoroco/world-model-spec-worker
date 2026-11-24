"""CPU route selection against sourced intersection and cycle-lane geometry.

This builds route candidates only. Original-frame body occupancy remains the
separate capture measurement in cycle_lane_intersection.py.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT


def _point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("two-dimensional point required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError("finite point coordinates required")
    return tuple(float(v) for v in value)


def _polygon(value):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("polygon with at least three vertices required")
    points = [_point(v) for v in value]
    area2 = sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points)))
    if abs(area2) < 1e-8:
        raise ValueError("nondegenerate polygon required")
    return points


def _inside(p, polygon):
    x, y = p
    inside = False
    for i, a in enumerate(polygon):
        b = polygon[(i + 1) % len(polygon)]
        cross = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
        if abs(cross) < 1e-9 and min(a[0], b[0]) - 1e-9 <= x <= max(a[0], b[0]) + 1e-9 and min(a[1], b[1]) - 1e-9 <= y <= max(a[1], b[1]) + 1e-9:
            return True
        if (a[1] > y) != (b[1] > y):
            edge_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < edge_x:
                inside = not inside
    return inside


def _breaks(a, b, polygon):
    dx, dy = b[0] - a[0], b[1] - a[1]
    out = []
    for i, c in enumerate(polygon):
        d = polygon[(i + 1) % len(polygon)]
        ex, ey = d[0] - c[0], d[1] - c[1]
        den = dx * ey - dy * ex
        if abs(den) < 1e-10:
            continue
        qx, qy = c[0] - a[0], c[1] - a[1]
        t = (qx * ey - qy * ex) / den
        u = (qx * dy - qy * dx) / den
        if 0 < t < 1 and 0 <= u <= 1:
            out.append(t)
    return out


def _route_flags(route, intersection, cycle_lane):
    in_intersection = in_cycle_lane = in_both = False
    for a, b in zip(route, route[1:]):
        if a == b:
            raise ValueError("zero-length route segment")
        cuts = sorted(set([0.0, 1.0] + _breaks(a, b, intersection) + _breaks(a, b, cycle_lane)))
        for lo, hi in zip(cuts, cuts[1:]):
            if hi - lo <= 1e-9:
                continue
            t = (lo + hi) / 2
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            j, c = _inside(p, intersection), _inside(p, cycle_lane)
            in_intersection |= j
            in_cycle_lane |= c
            in_both |= j and c
    return in_intersection, in_cycle_lane, in_both


def construct(site_path: str | Path, candidate_id: str, requested_overlap: bool) -> dict:
    """Select one source-bound route; fail if its geometry misses the case claim."""
    path = Path(site_path)
    raw = path.read_bytes()
    site = json.loads(raw)
    if site.get("assignment_id") != ASSIGNMENT or not site.get("map_id"):
        raise ValueError("assignment and source map identity required")
    if not site.get("intersection_id") or not site.get("cycle_lane_id"):
        raise ValueError("intersection and cycle-lane identities required")
    if site.get("cycle_lane_designated_for") not in ("bicycle", "electric_bicycle", "electric_scooter", "mixed_cycle"):
        raise ValueError("source cycle-lane designation required")
    if not site.get("designation_authority"):
        raise ValueError("cycle-lane designation authority required")
    intersection = _polygon(site.get("intersection_polygon"))
    cycle_lane = _polygon(site.get("cycle_lane_polygon"))
    candidates = site.get("route_candidates")
    if not isinstance(candidates, dict) or candidate_id not in candidates:
        raise ValueError("named route candidate required")
    raw_route = candidates[candidate_id]
    if not isinstance(raw_route, list) or len(raw_route) < 2:
        raise ValueError("route with two or more waypoints required")
    route = [_point(p) for p in raw_route]
    j, c, overlap = _route_flags(route, intersection, cycle_lane)
    if not j:
        raise ValueError("route does not cross source intersection")
    if not isinstance(requested_overlap, bool) or overlap != requested_overlap:
        raise ValueError("route does not match requested cycle-lane intersection overlap")
    return {"assignment_id": ASSIGNMENT, "map_id": site["map_id"],
            "intersection_id": site["intersection_id"], "cycle_lane_id": site["cycle_lane_id"],
            "designation_authority": site["designation_authority"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "candidate_id": candidate_id, "route_waypoints": raw_route,
            "route_crosses_intersection": j, "route_crosses_designated_cycle_lane": c,
            "route_centerline_overlaps_both": overlap,
            "limit": "Geometric route intent only; original motor-vehicle body occupancy and subsection 3 status require separate source readback."}
