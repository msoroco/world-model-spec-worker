"""Original body position on a separately reviewed intersection route.

The route document is an operator reviewed source, not a diagnostic map.  This
reader reports a measured signed station; it makes no visibility or legal claim.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class RouteReadError(ValueError):
    pass


def _xy(location):
    values = (getattr(location, "x", None), getattr(location, "y", None))
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise RouteReadError("original body position is not finite")
    return tuple(float(value) for value in values)


def _project(point, points):
    best = []
    station = 0.0
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 0.5:
            raise RouteReadError("reviewed route has a degenerate segment")
        t = min(1.0, max(0.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (length * length)))
        closest = (a[0] + t * dx, a[1] + t * dy)
        best.append((math.dist(point, closest), station + t * length))
        station += length
    best.sort()
    if not best or best[0][0] > 1.5:
        raise RouteReadError("original body is outside reviewed route corridor")
    if len(best) > 1 and abs(best[1][0] - best[0][0]) < 0.05 and abs(best[1][1] - best[0][1]) > 2:
        raise RouteReadError("original body route station is ambiguous")
    return best[0][1]


class ReviewedRouteReader:
    def __init__(self, site: dict, source_path: Path):
        source_path = Path(source_path)
        raw = source_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != site.get("ego_route_xy_source_sha256"):
            raise RouteReadError("reviewed route source hash differs from site")
        source = json.loads(raw)
        if (source.get("source_kind") != "ego_route_geometry" or
                not source.get("reviewer") or not source.get("source_citation") or
                source.get("route_xy") != site.get("ego_route_xy") or
                source.get("intersection_boundary_xy") != site.get("intersection_boundary_xy")):
            raise RouteReadError("reviewed route claim differs from site")
        points = source.get("route_xy")
        if (not isinstance(points, list) or len(points) < 3 or
                any(not isinstance(p, list) or len(p) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                    for p in points)):
            raise RouteReadError("reviewed route geometry invalid")
        exit_xy = source.get("traversal_exit_xy")
        if (not isinstance(exit_xy, list) or len(exit_xy) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in exit_xy)):
            raise RouteReadError("reviewed intersection exit missing")
        self.points = [tuple(map(float, p)) for p in points]
        self.boundary_station = _project(tuple(source["intersection_boundary_xy"]), self.points)
        self.exit_station = _project(tuple(exit_xy), self.points)
        if self.boundary_station < 30.48 or self.exit_station <= self.boundary_station + 1:
            raise RouteReadError("reviewed route cannot cover approach and traversal")
        self.last_frame = None

    def __call__(self, frame: int, snapshot, ego):
        if type(frame) is not int or snapshot.frame != frame:
            raise RouteReadError("route readback frame differs from original snapshot")
        if self.last_frame is not None and frame != self.last_frame + 1:
            raise RouteReadError("route readback original frame gap")
        transform = ego.get_transform()
        center_station = _project(_xy(transform.location), self.points)
        vertices = ego.bounding_box.get_world_vertices(transform)
        if len(vertices) != 8:
            raise RouteReadError("original body needs eight bounding vertices")
        stations = [_project(_xy(v), self.points) for v in vertices]
        traversing = max(stations) >= self.boundary_station and min(stations) <= self.exit_station
        self.last_frame = frame
        return self.boundary_station - center_station, traversing
