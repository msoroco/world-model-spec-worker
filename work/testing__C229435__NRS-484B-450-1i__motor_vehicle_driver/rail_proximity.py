"""Original-geometry vehicle-to-nearest-rail distance for parking review.

The 50-foot boundary is measured from the physical vehicle footprint,
not its center. Statutory traffic, law, officer and device exceptions stay
independent source questions.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C229435__NRS-484B-450-1i__motor_vehicle_driver"
FIFTY_FEET_M = 50 * 0.3048


def _point(p):
    if not isinstance(p, list) or len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p):
        raise ValueError("finite original geometry point required")
    return p


def _point_segment_distance(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    den = vx * vx + vy * vy
    if den == 0:
        raise ValueError("degenerate original segment")
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / den))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def _segments_intersect(a, b, c, d):
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0


def _segment_distance(a, b, c, d):
    if _segments_intersect(a, b, c, d):
        return 0.0
    return min(_point_segment_distance(a, c, d), _point_segment_distance(b, c, d),
               _point_segment_distance(c, a, b), _point_segment_distance(d, a, b))


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if packet.get("vehicle_action") not in ("stop", "stand", "park") or not packet.get("vehicle_actor_id"):
        raise ValueError("original vehicle action and identity required")
    footprint = packet.get("vehicle_footprint_m")
    if not isinstance(footprint, list) or len(footprint) < 3:
        raise ValueError("complete vehicle footprint required")
    footprint = [_point(p) for p in footprint]
    rails = packet.get("rail_polylines_m")
    if not isinstance(rails, list) or not rails:
        raise ValueError("original rail polylines required")
    distances = []
    for rail in rails:
        if not rail.get("rail_id") or not isinstance(rail.get("points_m"), list) or len(rail["points_m"]) < 2:
            raise ValueError("original rail identity and polyline required")
        points = [_point(p) for p in rail["points_m"]]
        distance = min(_segment_distance(footprint[i], footprint[(i + 1) % len(footprint)], points[j], points[j + 1])
                       for i in range(len(footprint)) for j in range(len(points) - 1))
        distances.append({"rail_id": rail["rail_id"], "vehicle_to_rail_distance_m": distance})
    nearest = min(distances, key=lambda x: x["vehicle_to_rail_distance_m"])
    exceptions = packet.get("exception_context")
    names = ("traffic_conflict_necessity", "law_compliance", "officer_direction", "official_device_direction")
    if not isinstance(exceptions, dict) or any(exceptions.get(n) not in ("present", "absent", "unresolved") for n in names):
        raise ValueError("independent statutory exception context required")
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "vehicle_action": packet["vehicle_action"], "vehicle_actor_id": packet["vehicle_actor_id"],
            "rail_distances": distances, "nearest_rail_id": nearest["rail_id"],
            "nearest_rail_distance_m": nearest["vehicle_to_rail_distance_m"],
            "fifty_feet_m": FIFTY_FEET_M,
            "within_fifty_feet": nearest["vehicle_to_rail_distance_m"] < FIFTY_FEET_M,
            "exception_context": exceptions,
            "review_limit": "Original rail identity, footprint and any exception need source review; a nearby other vehicle alone does not prove traffic-conflict necessity."}
