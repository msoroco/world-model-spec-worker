"""Lazy Native geometry sampler for the C125697 crossing-entry packet.

The intersection polygon must come from a verified Native map readback. This
module samples actual actor bounding boxes at each original world snapshot.
"""

from __future__ import annotations

import math


def _point(value):
    x, y = float(value.x), float(value.y)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("nonfinite Native footprint vertex")
    return x, y


def _hull(points):
    points = sorted(set(points))
    if len(points) < 3:
        raise ValueError("Native footprint has fewer than three distinct vertices")

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    lower = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    polygon = lower[:-1] + upper[:-1]
    if len(polygon) < 3:
        raise ValueError("Native footprint is degenerate")
    return polygon


def footprint_xy(actor):
    """Read CARLA actor's live world transform and bounding-box vertices."""
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) < 4:
        raise ValueError("Native actor bounding box lacks world vertices")
    return _hull([_point(vertex) for vertex in vertices])


def intersects_convex(left, right):
    """Inclusive convex polygon overlap, including edge contact."""
    left, right = _hull(left), _hull(right)
    for polygon in (left, right):
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            axis = (start[1] - end[1], end[0] - start[0])
            lproj = [p[0] * axis[0] + p[1] * axis[1] for p in left]
            rproj = [p[0] * axis[0] + p[1] * axis[1] for p in right]
            if max(lproj) < min(rproj) or max(rproj) < min(lproj):
                return False
    return True


def capture_frame(snapshot, actors, intersection_polygon):
    """Capture a single original frame after the world tick completes."""
    frame = snapshot.frame
    timestamp = snapshot.timestamp.elapsed_seconds
    if type(frame) is not int or not math.isfinite(timestamp):
        raise ValueError("invalid Native world snapshot identity/time")
    if set(actors) != {"ego", "other"} or actors["ego"].id == actors["other"].id:
        raise ValueError("two distinct Native actors required")
    states = {}
    for name, actor in actors.items():
        if not actor.is_alive:
            raise ValueError(f"{name}: actor no longer alive")
        footprint = footprint_xy(actor)
        states[name] = {
            "actor_id": actor.id,
            "footprint_xy_m": footprint,
            "footprint_intersects_intersection": intersects_convex(footprint, intersection_polygon),
        }
    return {"frame": frame, "timestamp_s": timestamp, "actors": states}
