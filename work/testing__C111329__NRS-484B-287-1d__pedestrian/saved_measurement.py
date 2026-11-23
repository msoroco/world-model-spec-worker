"""Independent original-frame crossing measurement; no legality evaluator."""
from __future__ import annotations

import math

from native_crossing import point


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def inside_polygon(p, polygon):
    x, y = point(p)
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if abs(_cross(a, b, (x, y))) < 1e-9 and min(a[0], b[0]) <= x <= max(a[0], b[0]) and min(a[1], b[1]) <= y <= max(a[1], b[1]):
            return False
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1]) + a[0]:
            inside = not inside
    return inside


def measure(plan: dict, frames: list[dict], device_observations: list[dict]) -> dict:
    """Require original continuous frames, observed walker and device readback."""
    if len(frames) < 3 or not device_observations:
        raise ValueError("original walker and device histories required")
    indexes = [f["original_frame"] for f in frames]
    if any(b != a + 1 for a, b in zip(indexes, indexes[1:])):
        raise ValueError("noncontiguous original frames")
    ids = {f.get("walker_id") for f in frames}
    if None in ids or len(ids) != 1:
        raise ValueError("walker identity discontinuity")
    polygon = [point(p) for p in plan["intersection_polygon"]]
    actual = [point(f["walker_center_xy"]) for f in frames]
    if math.dist(actual[0], point(plan["start"])) > 1.5 or math.dist(actual[-1], point(plan["end"])) > 1.5:
        raise ValueError("crossing endpoints not observed")
    if not any(inside_polygon(p, polygon) for p in actual):
        raise ValueError("no intersection traversal observed")
    by_frame = {d["original_frame"]: d for d in device_observations}
    if any(i not in by_frame for i in indexes):
        raise ValueError("device history incomplete")
    if any(not by_frame[i].get("source_sha256") or not by_frame[i].get("official_source") for i in indexes):
        raise ValueError("official device source missing")
    authorized = all(by_frame[i].get("pedestrian_governance") == "diagonal" and by_frame[i].get("state") == "permissive" for i in indexes if inside_polygon(actual[indexes.index(i)], polygon))
    return {"original_frame_start": indexes[0], "original_frame_end": indexes[-1], "walker_id": next(iter(ids)), "observed_start_xy": actual[0], "observed_end_xy": actual[-1], "observed_inside_frames": sum(inside_polygon(p, polygon) for p in actual), "authorization_observed_during_inside": authorized, "device_source_hashes": sorted({by_frame[i]["source_sha256"] for i in indexes}), "route_kind_planned": plan["route_kind"], "exception_484B_290": "unresolved"}
