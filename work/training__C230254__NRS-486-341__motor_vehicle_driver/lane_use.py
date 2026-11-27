"""Source-shape measurements for NRS 486.341; no legal classification.

Coordinates are metres in a common road-plane frame. Footprints and lane
polygons must be taken from the retained Native pose, bounding-box and map
sources. No clearance value in this module is a legal cutoff.
"""

from __future__ import annotations

from math import hypot, isfinite


def _polygon(points):
    vertices = [tuple(float(v) for v in point) for point in points]
    if len(vertices) < 3 or any(len(point) != 2 or not all(map(isfinite, point)) for point in vertices):
        raise ValueError("polygon needs at least three finite 2D vertices")
    if abs(_signed_area(vertices)) < 1e-9:
        raise ValueError("polygon area is zero")
    orientation = 1 if _signed_area(vertices) > 0 else -1
    for i, point in enumerate(vertices):
        following = vertices[(i + 1) % len(vertices)]
        after = vertices[(i + 2) % len(vertices)]
        if point == following:
            raise ValueError("polygon has a zero-length edge")
        cross = ((following[0] - point[0]) * (after[1] - following[1])
                 - (following[1] - point[1]) * (after[0] - following[0]))
        if orientation * cross < -1e-9:
            raise ValueError("polygon must be convex")
    return vertices


def _signed_area(points):
    return sum(x * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * y
               for i, (x, y) in enumerate(points)) / 2


def _clip(subject, boundary):
    """Intersect convex subject and convex boundary polygons."""
    result = list(subject)
    direction = 1 if _signed_area(boundary) > 0 else -1
    for i, start in enumerate(boundary):
        end = boundary[(i + 1) % len(boundary)]

        def side(point):
            return direction * ((end[0] - start[0]) * (point[1] - start[1])
                                - (end[1] - start[1]) * (point[0] - start[0]))

        previous = result[-1] if result else None
        output = []
        for current in result:
            if previous is not None:
                current_inside, previous_inside = side(current) >= -1e-9, side(previous) >= -1e-9
                if current_inside != previous_inside:
                    first, second = side(previous), side(current)
                    fraction = first / (first - second)
                    output.append((previous[0] + fraction * (current[0] - previous[0]),
                                   previous[1] + fraction * (current[1] - previous[1])))
                if current_inside:
                    output.append(current)
            previous = current
        result = output
    return result


def _segment_distance(a, b, c, d):
    def cross(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])

    def on(u, v, w):
        return min(u[0], v[0]) - 1e-9 <= w[0] <= max(u[0], v[0]) + 1e-9 and min(u[1], v[1]) - 1e-9 <= w[1] <= max(u[1], v[1]) + 1e-9

    if ((cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0)
            or (abs(cross(a, b, c)) < 1e-9 and on(a, b, c))
            or (abs(cross(a, b, d)) < 1e-9 and on(a, b, d))
            or (abs(cross(c, d, a)) < 1e-9 and on(c, d, a))
            or (abs(cross(c, d, b)) < 1e-9 and on(c, d, b))):
        return 0.0

    def point_segment(point, first, last):
        delta = (last[0] - first[0], last[1] - first[1])
        scale = max(0.0, min(1.0, ((point[0] - first[0]) * delta[0] + (point[1] - first[1]) * delta[1]) / (delta[0] ** 2 + delta[1] ** 2)))
        return hypot(point[0] - first[0] - scale * delta[0], point[1] - first[1] - scale * delta[1])

    return min(point_segment(a, c, d), point_segment(b, c, d), point_segment(c, a, b), point_segment(d, a, b))


def measure_frame(lane_polygon, motorcycle_footprint, ego_footprint):
    """Return raw spatial measurements from a synchronized Native frame.

    All three polygons must be convex; geometry and actor identities are
    separately source audited. No field says whether full lane use was denied.
    """
    lane, motorcycle, ego = map(_polygon, (lane_polygon, motorcycle_footprint, ego_footprint))
    motorcycle_area, ego_area = abs(_signed_area(motorcycle)), abs(_signed_area(ego))
    motorcycle_inside = _clip(motorcycle, lane)
    ego_inside = _clip(ego, lane)
    motorcycle_in_lane = abs(_signed_area(motorcycle_inside)) / motorcycle_area if motorcycle_inside else 0.0
    ego_in_lane = abs(_signed_area(ego_inside)) / ego_area if ego_inside else 0.0
    overlap = _clip(motorcycle, ego)
    if overlap and abs(_signed_area(overlap)) > 1e-9:
        gap = 0.0
    else:
        gap = min(_segment_distance(a, motorcycle[(i + 1) % len(motorcycle)], b, ego[(j + 1) % len(ego)])
                  for i, a in enumerate(motorcycle) for j, b in enumerate(ego))
    return {
        "motorcycle_footprint_area_m2": motorcycle_area,
        "ego_footprint_area_m2": ego_area,
        "motorcycle_lane_overlap_fraction": motorcycle_in_lane,
        "ego_lane_overlap_fraction": ego_in_lane,
        "footprint_surface_gap_m": gap,
        "footprint_overlap_area_m2": abs(_signed_area(overlap)) if overlap else 0.0,
    }


def measure_joined_frames(rows):
    """Measure contiguous synchronized frames with retained source references.

    A caller must first decode original Native actor/map sources into these rows.
    This function rejects joins with missing frames, time reversals or absent
    source references instead of manufacturing a plausible trace.
    """
    result = []
    for row in rows:
        frame = row.get("frame")
        time_s = row.get("time_s")
        references = row.get("source_refs")
        if not isinstance(frame, int) or isinstance(frame, bool) or frame < 0:
            raise ValueError("frame must be a nonnegative integer")
        if result and frame != result[-1]["frame"] + 1:
            raise ValueError("frame join is not contiguous")
        if not isinstance(time_s, (float, int)) or not isfinite(time_s):
            raise ValueError("time_s must be finite")
        if result and time_s <= result[-1]["time_s"]:
            raise ValueError("frame time is not increasing")
        if not isinstance(references, dict) or not all(references.get(key) for key in ("actor_trace", "actor_bounds", "lane_map")):
            raise ValueError("Native source references are missing")
        measured = measure_frame(row["lane_polygon"], row["motorcycle_footprint"], row["ego_footprint"])
        result.append({"frame": frame, "time_s": float(time_s), "source_refs": references, **measured})
    if not result:
        raise ValueError("no synchronized Native frames")
    return result
