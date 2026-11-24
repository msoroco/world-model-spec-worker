"""CPU construction and observation of a connected route past a barrier."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C230211__LVMC-11-22-020__motor_vehicle_driver"


def _point(raw):
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("two-dimensional point required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in raw):
        raise ValueError("finite point required")
    return (float(raw[0]), float(raw[1]))


def _rect(raw):
    if not isinstance(raw, list) or len(raw) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in raw):
        raise ValueError("finite barrier rectangle required")
    x0, y0, x1, y1 = map(float, raw)
    if x0 >= x1 or y0 >= y1:
        raise ValueError("nondegenerate barrier rectangle required")
    return x0, y0, x1, y1


def _distance(point, rect):
    x, y = point
    x0, y0, x1, y1 = rect
    return math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1))


def _context(site):
    if site.get("assignment_id") != ASSIGNMENT or not site.get("map_id"):
        raise ValueError("source assignment and map identity required")
    if not site.get("highway_id") or site.get("city_highway_status") not in ("established", "unresolved"):
        raise ValueError("highway-in-City source context required")
    if not site.get("barrier_id") or not site.get("barrier_geometry_source"):
        raise ValueError("physical barrier identity and source required")
    road = site.get("road_y_bounds")
    if not isinstance(road, list) or len(road) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in road) or road[0] >= road[1]:
        raise ValueError("road lateral bounds required")
    return _rect(site.get("barrier_rectangle")), tuple(map(float, road))


def construct(site_path: str | Path, candidate_id: str) -> dict:
    path = Path(site_path)
    raw = path.read_bytes()
    site = json.loads(raw)
    rect, (road_lo, road_hi) = _context(site)
    half_width = site.get("ego_half_width_m")
    if isinstance(half_width, bool) or not isinstance(half_width, (int, float)) or not math.isfinite(half_width) or half_width <= 0:
        raise ValueError("positive ego half-width required")
    routes = site.get("route_candidates")
    if not isinstance(routes, dict) or candidate_id not in routes:
        raise ValueError("named connected route required")
    raw_route = routes[candidate_id]
    if not isinstance(raw_route, list) or len(raw_route) < 2:
        raise ValueError("two or more route waypoints required")
    points = [_point(p) for p in raw_route]
    clearances = []
    for a, b in zip(points, points[1:]):
        if a == b:
            raise ValueError("zero-length route segment")
        count = max(1, math.ceil(math.dist(a, b) / 0.05))
        for i in range(count + 1):
            t = i / count
            point = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            if not road_lo + half_width <= point[1] <= road_hi - half_width:
                raise ValueError("route vehicle body leaves road bounds")
            clearance = _distance(point, rect) - half_width
            if clearance < 0:
                raise ValueError("route vehicle body intersects barrier")
            clearances.append(clearance)
    if not (points[0][0] < rect[0] and points[-1][0] > rect[2]):
        raise ValueError("route must approach and pass barrier")
    return {"assignment_id": ASSIGNMENT, "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "candidate_id": candidate_id, "barrier_id": site["barrier_id"],
            "highway_id": site["highway_id"], "city_highway_status": site["city_highway_status"],
            "route_waypoints": raw_route, "minimum_planned_body_clearance_m": min(clearances),
            "limit": "Sampled geometric clearance is an engineering check, not an imprudence cutoff or realized motion."}


def measure(trace_path: str | Path) -> dict:
    path = Path(trace_path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    rect, _ = _context(packet)
    if not packet.get("original_trace_id") or not packet.get("ego_actor_id") or not packet.get("driver_actor_id"):
        raise ValueError("original vehicle, driver and trace identities required")
    if not packet.get("surrounding_conditions_source"):
        raise ValueError("surrounding conditions source required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    observations = []
    previous = None
    for i, frame in enumerate(frames):
        t, speed = frame.get("time_s"), frame.get("speed_mps")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (t, speed)) or speed < 0:
            raise ValueError("finite nonnegative original time and speed required")
        if previous is not None and not 0 < t - previous <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        previous = t
        vertices = frame.get("ego_footprint_vertices")
        if not isinstance(vertices, list) or len(vertices) != 4:
            raise ValueError("four original ego footprint vertices required")
        corners = [_point(p) for p in vertices]
        observations.append({"frame_index": i, "time_s": t, "speed_mps": speed,
                             "minimum_vertex_to_barrier_m": min(_distance(p, rect) for p in corners),
                             "barrier_contact_reported": frame.get("barrier_contact") is True})
    return {"assignment_id": ASSIGNMENT, "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "original_trace_id": packet["original_trace_id"], "ego_actor_id": packet["ego_actor_id"],
            "driver_actor_id": packet["driver_actor_id"], "barrier_id": packet["barrier_id"],
            "highway_id": packet["highway_id"], "city_highway_status": packet["city_highway_status"],
            "surrounding_conditions_source": packet["surrounding_conditions_source"],
            "observations": observations,
            "review_limit": "Barrier clearance, speed and contact observations do not decide careless or imprudent driving."}
