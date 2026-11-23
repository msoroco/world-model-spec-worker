"""Source-bound route geometry for LVMC 11.30.050; no legal verdicts."""
from __future__ import annotations

import math


def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("a point needs two coordinates")
    x, y = map(float, value)
    if not all(map(math.isfinite, (x, y))):
        raise ValueError("nonfinite coordinate")
    return x, y


def segment(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("a curb segment needs two endpoints")
    a, b = map(point, value)
    if math.dist(a, b) <= 0:
        raise ValueError("zero-length curb")
    return a, b


def nearest_on_segment(start, curb):
    """Closest point on the supplied finite opposite curb, including endpoints."""
    p = point(start)
    a, b = segment(curb)
    vx, vy = b[0]-a[0], b[1]-a[1]
    u = max(0.0, min(1.0, ((p[0]-a[0])*vx+(p[1]-a[1])*vy)/(vx*vx+vy*vy)))
    return [a[0]+u*vx, a[1]+u*vy], u


def route_measurement(route, starting_curb, opposite_curb):
    """Measure original route against sourced curbs; preserve uncertainty."""
    if len(route) < 2:
        raise ValueError("crossing needs start and exit")
    path = [point(p) for p in route]
    a, b = segment(starting_curb)
    segment(opposite_curb)
    tx, ty = b[0]-a[0], b[1]-a[1]
    dx, dy = path[-1][0]-path[0][0], path[-1][1]-path[0][1]
    chord = math.hypot(dx, dy)
    if chord == 0:
        raise ValueError("zero-displacement crossing")
    polyline = sum(math.dist(u, v) for u, v in zip(path, path[1:]))
    shortest_point, fraction = nearest_on_segment(path[0], opposite_curb)
    minimum = math.dist(path[0], shortest_point)
    # Magnitude avoids choosing a curb normal or crossing direction.
    cosine_to_curb = abs((dx*tx+dy*ty)/(chord*math.hypot(tx, ty)))
    cosine_to_curb = min(1.0, max(0.0, cosine_to_curb))
    return {
        "route_points_xy_m": [list(p) for p in path],
        "entry_xy_m": list(path[0]), "exit_xy_m": list(path[-1]),
        "route_length_m": polyline, "entry_exit_chord_m": chord,
        "angle_to_starting_curb_deg": math.degrees(math.acos(cosine_to_curb)),
        "shortest_opposite_curb_point_xy_m": shortest_point,
        "shortest_opposite_curb_fraction": fraction,
        "shortest_geometric_distance_m": minimum,
        "route_excess_over_geometric_minimum_m": polyline-minimum,
        "legal_route_classification": "unresolved",
    }


def _point_in_polygon(p, polygon):
    x, y = p
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay = a
        bx, by = b
        cross = (x-ax)*(by-ay)-(y-ay)*(bx-ax)
        if abs(cross) <= 1e-9 and min(ax, bx)-1e-9 <= x <= max(ax, bx)+1e-9 and min(ay, by)-1e-9 <= y <= max(ay, by)+1e-9:
            return True
        if (ay > y) != (by > y):
            at_x = ax + (y-ay)*(bx-ax)/(by-ay)
            if x < at_x:
                inside = not inside
    return inside


def _segments_intersect(a, b, c, d):
    def orient(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    ab_c = orient(a, b, c)
    ab_d = orient(a, b, d)
    cd_a = orient(c, d, a)
    cd_b = orient(c, d, b)
    if not (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])) and
            max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1]))):
        return False
    return ab_c*ab_d <= 0 and cd_a*cd_b <= 0


def crosswalk_overlap(route, polygons):
    path = [point(p) for p in route]
    for polygon in polygons:
        poly = [point(p) for p in polygon]
        if any(_point_in_polygon(p, poly) for p in path):
            return True
        for a, b in zip(path, path[1:]):
            if any(_segments_intersect(a, b, c, d) for c, d in zip(poly, poly[1:] + poly[:1])):
                return True
    return False


def validate_scene(scene):
    if scene.get("actor") != "pedestrian":
        raise ValueError("exact pedestrian actor required")
    for key in ("starting_curb_xy_m", "opposite_curb_xy_m"):
        segment(scene[key])
    measured = route_measurement(scene["route_xy_m"], scene["starting_curb_xy_m"], scene["opposite_curb_xy_m"])
    bounds = scene.get("crosswalk_boundaries_xy_m")
    if not isinstance(bounds, list) or not bounds:
        raise ValueError("marked and unmarked crosswalk inventory required")
    for polygon in bounds:
        if len(polygon) < 3:
            raise ValueError("crosswalk polygon needs at least three vertices")
        [point(vertex) for vertex in polygon]
    if scene.get("crosswalk_context") not in ("inside", "outside"):
        raise ValueError("crosswalk context required")
    inside = crosswalk_overlap(scene["route_xy_m"], bounds)
    if inside != (scene["crosswalk_context"] == "inside"):
        raise ValueError("authored route and crosswalk geometry disagree")
    if not scene.get("jurisdiction_source") or not scene.get("curb_source"):
        raise ValueError("jurisdiction and curb provenance required")
    if scene.get("control_context") is None:
        raise ValueError("governing control context required")
    return measured


def measure_original_history(rows, scene):
    """Reject missing original frame joins; requested waypoints cannot stand in for motion."""
    validate_scene(scene)
    if not rows:
        raise ValueError("original walker body history missing")
    frames = [row.get("frame") for row in rows]
    if any(type(frame) is not int for frame in frames) or len(set(frames)) != len(frames) or frames != sorted(frames):
        raise ValueError("original walker frames invalid")
    if any(row.get("source") != "original_native" for row in rows):
        raise ValueError("original Native walker source required")
    if any(row.get("actor_id") != rows[0].get("actor_id") for row in rows):
        raise ValueError("walker identity changed")
    route = [point(row["body_center_xy_m"]) for row in rows]
    if len(route) < 2:
        raise ValueError("complete crossing history required")
    if crosswalk_overlap(route, scene["crosswalk_boundaries_xy_m"]) != (scene["crosswalk_context"] == "inside"):
        raise ValueError("original route and crosswalk context disagree")
    out = route_measurement(route, scene["starting_curb_xy_m"], scene["opposite_curb_xy_m"])
    out.update({"first_frame": frames[0], "last_frame": frames[-1],
                "original_frame_count": len(frames), "actor_id": rows[0]["actor_id"],
                "crosswalk_context": scene["crosswalk_context"],
                "source_kind": "original_native"})
    return out
