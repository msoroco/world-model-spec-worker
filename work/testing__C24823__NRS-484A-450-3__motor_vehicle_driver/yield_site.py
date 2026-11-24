"""CPU construction of the yield-sign stopping-reference hierarchy.

Distances and geometric sight rays are engineering observations. They do not
decide when stopping is required for safety or define a statutory view cutoff.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C24823__NRS-484A-450-3__motor_vehicle_driver"


def _point(raw):
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("two-dimensional point required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in raw):
        raise ValueError("finite point required")
    return (float(raw[0]), float(raw[1]))


def _blocked(a, b, rect):
    """True when the open sight segment enters a solid axis-aligned occluder."""
    x0, y0, x1, y1 = rect
    if not x0 < x1 or not y0 < y1:
        raise ValueError("nondegenerate occluder bounds required")
    lo, hi = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo > hi:
            return False
    return lo < 1 - 1e-9 and hi > 1e-9


def select_stop_reference(site_path: str | Path) -> dict:
    path = Path(site_path)
    raw = path.read_bytes()
    site = json.loads(raw)
    if site.get("assignment_id") != ASSIGNMENT or not site.get("map_id"):
        raise ValueError("source assignment and map identity required")
    if site.get("control") != "yield_sign" or not site.get("yield_sign_id"):
        raise ValueError("source yield-sign governance required")
    if site.get("vehicle_type") != "motor_vehicle" or not site.get("ego_actor_id"):
        raise ValueError("source motor-vehicle identity required")
    if not site.get("intersecting_highway_id") or not site.get("approach_roadway_id"):
        raise ValueError("source qualifying highway and approach required")
    if site.get("stopping_required_for_safety") not in ("yes", "no", "unresolved"):
        raise ValueError("separate safety-necessity review required")
    crosswalk = site.get("nearest_crosswalk_position")
    stop_line = site.get("marked_stop_line_position")
    if crosswalk is not None:
        reference_kind, point = "nearest_crosswalk", _point(crosswalk)
    elif stop_line is not None:
        reference_kind, point = "marked_stop_line", _point(stop_line)
    else:
        traffic = [_point(p) for p in site.get("approaching_traffic_points", [])]
        if not traffic:
            raise ValueError("approaching traffic sight targets required")
        occluders = site.get("occluders")
        if not isinstance(occluders, list) or not occluders:
            raise ValueError("constructed blind-approach occluder required")
        rectangles = []
        for rect in occluders:
            if not isinstance(rect, list) or len(rect) != 4:
                raise ValueError("occluder rectangle required")
            values = [float(v) for v in rect]
            if any(not math.isfinite(v) for v in values):
                raise ValueError("finite occluder required")
            rectangles.append(values)
        boundary = site.get("intersecting_highway_boundary_x")
        if isinstance(boundary, bool) or not isinstance(boundary, (int, float)) or not math.isfinite(boundary):
            raise ValueError("source intersecting-highway boundary required")
        candidates = site.get("driver_viewpoint_candidates")
        if not isinstance(candidates, list) or len(candidates) < 2:
            raise ValueError("multiple driver viewpoint candidates required")
        visible = []
        for candidate in candidates:
            if not candidate.get("id"):
                raise ValueError("candidate identity required")
            p = _point(candidate.get("position"))
            if p[0] >= boundary:
                raise ValueError("candidate must precede intersecting highway")
            seen = any(not any(_blocked(p, target, r) for r in rectangles) for target in traffic)
            if seen:
                visible.append((boundary - p[0], candidate["id"], p))
        if not visible:
            raise ValueError("no candidate with an unobstructed sight ray")
        _, selected_id, point = min(visible)
        reference_kind = "nearest_point_with_geometric_view"
    return {"assignment_id": ASSIGNMENT, "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "map_id": site["map_id"], "yield_sign_id": site["yield_sign_id"],
            "intersecting_highway_id": site["intersecting_highway_id"],
            "reference_kind": reference_kind, "reference_position": list(point),
            "selected_candidate_id": selected_id if reference_kind == "nearest_point_with_geometric_view" else None,
            "stopping_required_for_safety": site["stopping_required_for_safety"],
            "limit": "Geometric construction only; original driver viewpoint, sight and actual stopping remain to be captured and independently reviewed."}
