"""Original body station and occupancy on a separately reviewed railway route."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _point(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("reviewed rail route coordinate invalid")
    return float(value[0]), float(value[1])


def _station(xy, points):
    candidates = []
    station = 0.0
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < .5:
            raise ValueError("reviewed rail route segment degenerate")
        t = min(1.0, max(0.0, ((xy[0] - a[0]) * dx + (xy[1] - a[1]) * dy) / length ** 2))
        closest = a[0] + t * dx, a[1] + t * dy
        candidates.append((math.dist(xy, closest), station + t * length))
        station += length
    candidates.sort()
    if not candidates or candidates[0][0] > 1.5:
        raise ValueError("original rail body outside reviewed route corridor")
    if (len(candidates) > 1 and abs(candidates[0][0] - candidates[1][0]) < .05 and
            abs(candidates[0][1] - candidates[1][1]) > 2):
        raise ValueError("original rail route station ambiguous")
    return candidates[0][1]


class ReviewedRailRouteReader:
    def __init__(self, site, source_path):
        source_path = Path(source_path)
        raw = source_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != site.get("route_source_sha256"):
            raise ValueError("reviewed rail route source hash differs")
        source = json.loads(raw)
        if (source.get("source_kind") != "rail_crossing_route" or
                not source.get("reviewer") or not source.get("source_citation") or
                source.get("road_sha256") != site.get("road_sha256")):
            raise ValueError("reviewed rail route identity or citation missing")
        points = source.get("route_xy")
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError("reviewed rail route geometry missing")
        self.points = [_point(point) for point in points]
        self.entry = _station(_point(source.get("crossing_entry_xy")), self.points)
        self.exit = _station(_point(source.get("crossing_exit_xy")), self.points)
        if self.entry < 30.48 or self.exit <= self.entry + 1:
            raise ValueError("reviewed rail route lacks 100-foot approach or traversal")
        self.last_frame = None

    def __call__(self, frame, snapshot, ego):
        if (type(frame) is not int or snapshot.frame != frame or
                (self.last_frame is not None and frame != self.last_frame + 1)):
            raise ValueError("original rail route frame join differs")
        transform = ego.get_transform()
        location = transform.location
        center = _station(_point((location.x, location.y)), self.points)
        vertices = ego.bounding_box.get_world_vertices(transform)
        if len(vertices) != 8:
            raise ValueError("original rail body needs eight bounding vertices")
        stations = [_station(_point((v.x, v.y)), self.points) for v in vertices]
        occupancy = max(stations) >= self.entry and min(stations) <= self.exit
        self.last_frame = frame
        return center, occupancy
