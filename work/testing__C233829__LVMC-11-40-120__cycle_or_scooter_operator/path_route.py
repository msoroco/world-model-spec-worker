"""Construct named rider routes inside source-designated path or roadway bounds."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from path_observation import ASSIGNMENT


def _point(raw):
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("two-dimensional point required")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in raw):
        raise ValueError("finite point required")
    return tuple(float(x) for x in raw)


def _polygon(raw):
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError("polygon required")
    points = [_point(p) for p in raw]
    area2 = sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points)))
    if abs(area2) < 1e-8:
        raise ValueError("nondegenerate polygon required")
    return points


def _inside(point, polygon):
    x, y = point
    inside = False
    for i, a in enumerate(polygon):
        b = polygon[(i + 1) % len(polygon)]
        cross = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
        if abs(cross) < 1e-9 and min(a[0], b[0]) - 1e-9 <= x <= max(a[0], b[0]) + 1e-9 and min(a[1], b[1]) - 1e-9 <= y <= max(a[1], b[1]) + 1e-9:
            return True
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                inside = not inside
    return inside


def select_route(site_path: str | Path, candidate_id: str, target: str) -> dict:
    """Require a route's waypoints and segment interiors in its named facility."""
    path = Path(site_path)
    raw = path.read_bytes()
    site = json.loads(raw)
    if site.get("assignment_id") != ASSIGNMENT or not site.get("map_id"):
        raise ValueError("source assignment and map identity required")
    if not site.get("roadway_id") or not site.get("path_id") or not site.get("path_designation_source"):
        raise ValueError("source roadway and designated path identities required")
    if site.get("path_adjacent_to_roadway") is not True or site.get("sidewalk_status") != "absent":
        raise ValueError("adjacent path and absent sidewalk required for assigned cell")
    if site.get("path_usability_status") not in ("usable", "unusable", "unresolved"):
        raise ValueError("path usability context required")
    if target not in ("path", "roadway"):
        raise ValueError("target facility must be path or roadway")
    polygon = _polygon(site.get(target + "_polygon"))
    candidates = site.get("route_candidates")
    if not isinstance(candidates, dict) or candidate_id not in candidates:
        raise ValueError("named route candidate required")
    raw_route = candidates[candidate_id]
    if not isinstance(raw_route, list) or len(raw_route) < 2:
        raise ValueError("two or more route waypoints required")
    route = [_point(p) for p in raw_route]
    for a, b in zip(route, route[1:]):
        if a == b:
            raise ValueError("zero-length route segment")
        distance = math.dist(a, b)
        count = max(1, math.ceil(distance / 0.25))
        for i in range(count + 1):
            t = i / count
            point = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            if not _inside(point, polygon):
                raise ValueError("route leaves target facility polygon")
    return {"assignment_id": ASSIGNMENT, "map_id": site["map_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "candidate_id": candidate_id, "target_facility": target,
            "roadway_id": site["roadway_id"], "path_id": site["path_id"],
            "path_designation_source": site["path_designation_source"],
            "path_usability_status": site["path_usability_status"],
            "route_waypoints": raw_route,
            "limit": "Engineering centerline selection only; original rider body position and path usability need independent source readback."}
