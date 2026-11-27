"""Measure original body contact with a reviewed sidewalk and entrance patches.

The output is physical evidence. It never decides whether a statutory exception
applies, because vehicle design and operator duty need independent source review.
"""

from __future__ import annotations

import math


def polygon(value):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("original polygon needs at least three vertices")
    for point in value:
        if (not isinstance(point, list) or len(point) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                    not math.isfinite(v) for v in point)):
            raise ValueError("original polygon needs finite planar vertices")
    area = signed_area(value)
    if abs(area) <= 1e-6:
        raise ValueError("original polygon has zero area")
    signs = [cross(value[i], value[(i + 1) % len(value)],
                   value[(i + 2) % len(value)]) for i in range(len(value))]
    if not (all(v >= -1e-8 for v in signs) or
            all(v <= 1e-8 for v in signs)):
        raise ValueError("original polygon must be convex")
    return value


def cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def signed_area(points):
    return sum(points[i][0] * points[(i + 1) % len(points)][1] -
               points[(i + 1) % len(points)][0] * points[i][1]
               for i in range(len(points))) / 2


def overlap_area(subject, clip):
    subject, clip = polygon(subject), polygon(clip)
    direction = 1 if signed_area(clip) > 0 else -1
    result = subject
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        old, result = result, []
        if not old:
            break
        for j, q in enumerate(old):
            p = old[j - 1]
            cp, cq = direction * cross(a, b, p), direction * cross(a, b, q)
            if (cp >= 0) != (cq >= 0):
                t = cp / (cp - cq)
                result.append([p[0] + t * (q[0] - p[0]),
                               p[1] + t * (q[1] - p[1])])
            if cq >= 0:
                result.append(q)
    return abs(signed_area(result)) if len(result) >= 3 else 0.0


def measure_frame(row, site):
    """Use original geometry only; report area without a legal cutoff."""
    for key in ("original_frame", "time_s", "vehicle_actor_id",
                "body_polygon_xy", "body_geometry_source_sha256"):
        if row.get(key) is None:
            raise ValueError("missing original body source: " + key)
    if row["body_geometry_source_sha256"] != site.get("body_geometry_source_sha256"):
        raise ValueError("original body source differs from reviewed site")
    sidewalk = polygon(site.get("sidewalk_area_polygon_xy"))
    area = overlap_area(row["body_polygon_xy"], sidewalk)
    entrances = site.get("entrance_polygons_xy")
    if not isinstance(entrances, dict):
        raise ValueError("reviewed entrance inventory missing")
    entrance_areas = {kind: overlap_area(row["body_polygon_xy"], poly)
                      for kind, poly in entrances.items()}
    return {"original_frame": row["original_frame"],
            "time_s": row["time_s"],
            "vehicle_actor_id": row["vehicle_actor_id"],
            "sidewalk_overlap_area_m2": area,
            "entrance_overlap_area_m2": entrance_areas,
            "measurement_limit": "Physical areas only; no legal overlap threshold or exception verdict."}
