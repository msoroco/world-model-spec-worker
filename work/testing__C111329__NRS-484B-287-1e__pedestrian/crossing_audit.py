"""Independent source-history audit for diagonal pedestrian comparisons."""
from __future__ import annotations

import math


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("missing measured XY")
    xy = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in xy):
        raise ValueError("nonfinite XY")
    return xy


def _on_segment(point, a, b):
    cross = (b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])
    return abs(cross) <= 1e-7 and min(a[0], b[0]) <= point[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])


def _inside(point, polygon):
    if any(_on_segment(point, a, b) for a, b in zip(polygon, polygon[1:]+polygon[:1])):
        return True
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside


def audit_history(plan, crossing_polygon, walker_frames, device_frames):
    """Summarize only original observed frames; reject missing synchronized sources."""
    if len(walker_frames) < 3 or len(walker_frames) != len(device_frames):
        raise ValueError("complete walker/device frame histories required")
    polygon = [_point(p) for p in crossing_polygon]
    if len(polygon) < 4:
        raise ValueError("crossing polygon required")
    indexes = [w["original_frame"] for w in walker_frames]
    if any(b != a+1 for a, b in zip(indexes, indexes[1:])):
        raise ValueError("walker frame gap")
    if [d["original_frame"] for d in device_frames] != indexes:
        raise ValueError("device/walker frame misalignment")
    walker_ids = {w.get("walker_id") for w in walker_frames}
    if len(walker_ids) != 1 or None in walker_ids:
        raise ValueError("walker identity discontinuity")
    positions = [_point(w["center_xy"]) for w in walker_frames]
    if math.dist(positions[0], _point(plan["start_xy"])) > 1.5 or math.dist(positions[-1], _point(plan["destination_xy"])) > 1.5:
        raise ValueError("opposite-corner traversal endpoints not observed")
    crossing = [i for i, p in enumerate(positions) if _inside(p, polygon)]
    if not crossing:
        raise ValueError("no observed crossing footprint")
    states = []
    for i in crossing:
        device = device_frames[i]
        if device.get("device_id") != plan["device_id"] or not device.get("source_sha256"):
            raise ValueError("governing device identity/source absent")
        if device.get("pedestrian_governance") != "diagonal":
            raise ValueError("device state not for diagonal pedestrians")
        if not device.get("instruction"):
            raise ValueError("observed diagonal instruction missing")
        states.append(device["instruction"])
    return {"walker_id": next(iter(walker_ids)), "original_frame_start": indexes[0],
            "original_frame_end": indexes[-1], "crossing_frames": [indexes[i] for i in crossing],
            "observed_instructions": states, "device_id": plan["device_id"],
            "all_crossing_frames_permissive": all(s == "diagonal_walk" for s in states),
            "source_sha256": plan["source_sha256"],
            "exception_484b_290_review": plan["exception_484b_290_review"],
            "legal_conclusion": "not_assessed"}


def audit_comparison(reference, variant):
    """Check the declared device-instruction intervention without legal labels."""
    for key in ("walker_id", "device_id", "source_sha256", "exception_484b_290_review"):
        if reference.get(key) != variant.get(key):
            raise ValueError(f"fixed comparison condition changed: {key}")
    if reference.get("crossing_frames") != variant.get("crossing_frames"):
        raise ValueError("crossing timing/geometry differs across comparison")
    if not reference.get("all_crossing_frames_permissive") or variant.get("all_crossing_frames_permissive"):
        raise ValueError("device-instruction contrast unobserved")
    return {"comparison_verified": True,
            "deliberate_difference": "observed diagonal pedestrian instruction during original crossing frames",
            "legal_conclusion": "not_assessed"}
