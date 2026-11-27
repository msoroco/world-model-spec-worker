"""Original body footprint against a reviewed center-turn-lane polygon.

This produces observable lane geometry only. The polygon must be bound to the
reviewed original map by the caller; its use does not decide statutory compliance.
"""

from math import isfinite


def _point(value):
    if len(value) < 2:
        raise ValueError("original footprint coordinate missing")
    point = (float(value[0]), float(value[1]))
    if not all(isfinite(axis) for axis in point):
        raise ValueError("original footprint coordinate nonfinite")
    return point


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _hull(points):
    unique = sorted(set(points))
    if len(unique) < 3:
        raise ValueError("original body footprint degenerate")
    lower = []
    for point in unique:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    result = lower[:-1] + upper[:-1]
    if len(result) < 3:
        raise ValueError("original body footprint collinear")
    return result


def _inside(point, polygon):
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if abs(_cross(a, b, point)) < 1e-9 and min(a[0], b[0]) <= point[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= point[1] <= max(a[1], b[1]):
            return True
        if (a[1] > point[1]) != (b[1] > point[1]):
            x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < x:
                inside = not inside
    return inside


def _edges_intersect(a, b, c, d):
    o1, o2, o3, o4 = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    if all(abs(value) < 1e-9 for value in (o1, o2, o3, o4)):
        return (max(min(a[0], b[0]), min(c[0], d[0])) <=
                min(max(a[0], b[0]), max(c[0], d[0])) and
                max(min(a[1], b[1]), min(c[1], d[1])) <=
                min(max(a[1], b[1]), max(c[1], d[1])))
    return (o1 <= 0 <= o2 or o2 <= 0 <= o1) and (o3 <= 0 <= o4 or o4 <= 0 <= o3)


def body_occupancy(lane_polygon_xy_m, original_body_vertices_m):
    """Return overlap and containment from all eight Native body vertices."""
    if len(lane_polygon_xy_m) < 4 or len(original_body_vertices_m) != 8:
        raise ValueError("reviewed lane polygon or eight original body vertices missing")
    lane = [_point(point) for point in lane_polygon_xy_m]
    body = _hull([_point(vertex) for vertex in original_body_vertices_m])
    if len(set(lane)) < 4:
        raise ValueError("reviewed lane polygon degenerate")
    within = all(_inside(point, lane) for point in body)
    overlaps = within or any(_inside(point, lane) for point in body) or any(
        _inside(point, body) for point in lane)
    if not overlaps:
        overlaps = any(_edges_intersect(a, b, c, d)
                       for a, b in zip(body, body[1:] + body[:1])
                       for c, d in zip(lane, lane[1:] + lane[:1]))
    return {"body_overlaps_center_lane": overlaps, "body_within_center_lane": within}
