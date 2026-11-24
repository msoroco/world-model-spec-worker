"""Source-bound overlap of a parked motor vehicle and sidewalk area.

The local sidewalk patch must be a convex original geometry polygon.
Statutory exceptions and the distinct bicycle/scooter allowance are not
inferred from this physical overlap.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C229462__NRS-484B-450-1a__motor_vehicle_driver"


def _points(value):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("complete polygon required")
    for p in value:
        if not isinstance(p, list) or len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p):
            raise ValueError("finite original polygon points required")
    return value


def _cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _area(points):
    return sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points))) / 2


def _convex(points):
    signs = [_cross(points[i], points[(i + 1) % len(points)], points[(i + 2) % len(points)]) for i in range(len(points))]
    return all(x >= -1e-9 for x in signs) or all(x <= 1e-9 for x in signs)


def _clip(subject, clip):
    direction = 1 if _area(clip) > 0 else -1
    out = subject
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        previous = out
        out = []
        if not previous:
            break
        for j, q in enumerate(previous):
            p = previous[j - 1]
            cp, cq = direction * _cross(a, b, p), direction * _cross(a, b, q)
            if (cp >= 0) != (cq >= 0):
                t = cp / (cp - cq)
                out.append([p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])])
            if cq >= 0:
                out.append(q)
    return out


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if packet.get("vehicle_type") != "motor_vehicle" or not packet.get("vehicle_actor_id"):
        raise ValueError("motor vehicle identity required for assigned branch")
    if packet.get("vehicle_action") not in ("stop", "stand", "park") or not packet.get("sidewalk_area_id"):
        raise ValueError("original action and sidewalk identity required")
    vehicle, sidewalk = _points(packet.get("vehicle_footprint_m")), _points(packet.get("sidewalk_patch_m"))
    if not _convex(vehicle) or not _convex(sidewalk) or abs(_area(vehicle)) < 1e-6 or abs(_area(sidewalk)) < 1e-6:
        raise ValueError("nondegenerate convex original patches required")
    overlap = _clip(vehicle, sidewalk)
    overlap_area = abs(_area(overlap)) if len(overlap) >= 3 else 0.0
    names = ("traffic_conflict_necessity", "law_compliance", "officer_direction", "official_device_direction", "subsection_3")
    exceptions = packet.get("exception_context")
    if not isinstance(exceptions, dict) or any(exceptions.get(n) not in ("present", "absent", "unresolved") for n in names):
        raise ValueError("independent exception context required")
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "vehicle_actor_id": packet["vehicle_actor_id"], "sidewalk_area_id": packet["sidewalk_area_id"],
            "vehicle_action": packet["vehicle_action"], "physical_overlap_area_m2": overlap_area,
            "vehicle_footprint_on_sidewalk": overlap_area > 1e-6,
            "exception_context": exceptions,
            "review_limit": "A sidewalk overlap is physical evidence only. Review site identity, action and each statutory exception independently; the bicycle/scooter allowance is not a motor-vehicle allowance."}
