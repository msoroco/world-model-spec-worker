"""Lazy original-world footprint sampler for the C125714 crossing.

The caller must bind the reviewed map, crossing polygon and actor IDs before
recording. This module never fabricates an intersection or legal context.
"""
from __future__ import annotations

import math


def capture_pair(snapshot, actors: dict) -> dict:
    if set(actors) != {"ego", "other"} or actors["ego"].id == actors["other"].id:
        raise ValueError("two distinct Native vehicle actors required")
    frame = snapshot.frame
    time_s = snapshot.timestamp.elapsed_seconds
    if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
        raise ValueError("invalid original Native snapshot identity/time")
    result = {}
    for name in ("ego", "other"):
        actor = actors[name]
        if not actor.is_alive:
            raise ValueError(name + ": original actor is not alive")
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        if len(vertices) < 4:
            raise ValueError(name + ": original bounding box missing")
        xy = []
        for vertex in vertices:
            if not all(math.isfinite(v) for v in (vertex.x, vertex.y, vertex.z)):
                raise ValueError(name + ": nonfinite original body vertex")
            point = [float(vertex.x), float(vertex.y)]
            if point not in xy:
                xy.append(point)
        if len(xy) < 4:
            raise ValueError(name + ": original footprint degenerate")
        # Monotone-chain hull orders CARLA's eight 3D corners into one 2D body.
        points = sorted(tuple(p) for p in xy)
        def cross(a, b, c):
            return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
        lower, upper = [], []
        for point in points:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
                lower.pop()
            lower.append(point)
        for point in reversed(points):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
                upper.pop()
            upper.append(point)
        hull = lower[:-1] + upper[:-1]
        if len(hull) < 3:
            raise ValueError(name + ": original footprint hull degenerate")
        result[name] = {"frame": frame, "time_s": time_s, "actor_id": actor.id,
                        "body_vertices_xy_m": [list(p) for p in hull]}
    return result


def append_pair(streams: dict, sample: dict) -> None:
    """Append the same original tick to both JSONL streams in owned attempt."""
    import json
    if set(streams) != {"ego", "other"} or set(sample) != {"ego", "other"}:
        raise ValueError("both original participant streams required")
    if (sample["ego"]["frame"], sample["ego"]["time_s"]) != (
            sample["other"]["frame"], sample["other"]["time_s"]):
        raise ValueError("original capture frame/time join differs")
    for name in ("ego", "other"):
        streams[name].write(json.dumps(sample[name], allow_nan=False) + "\n")
