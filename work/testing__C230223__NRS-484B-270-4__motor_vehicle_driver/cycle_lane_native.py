"""Source-gated Native route construction and deterministic control policy.

This module prepares a CARLA route from reviewed site/exception/vehicle packets.
The actual world and four-camera capture still need a Native runner.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT
from cycle_lane_site import construct

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _read(path: Path, expected: str) -> dict:
    if (path.is_symlink() or not path.is_file() or not isinstance(expected, str) or
            len(expected) != 64 or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
        raise ValueError("reviewed source hash missing or changed: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(case_id: str, site_path: str | Path, site_sha256: str,
            exception_path: str | Path, exception_sha256: str,
            vehicle_path: str | Path, vehicle_sha256: str,
            route_candidate_id: str) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    case = next((c for c in plan["cases"] if c["case_id"] == case_id), None)
    if case is None:
        raise ValueError("exact selected case required")
    site = _read(Path(site_path), site_sha256)
    exception = _read(Path(exception_path), exception_sha256)
    vehicle = _read(Path(vehicle_path), vehicle_sha256)
    if (site.get("assignment_id") != ASSIGNMENT or
            site.get("source_kind") != "original_reviewed" or
            site.get("intersection_is_public_highway_junction") is not True or
            site.get("not_alley_junction") is not True or
            not site.get("designation_authority")):
        raise ValueError("reviewed public intersection and lane designation required")
    if (exception.get("source_kind") != "original_reviewed" or
            exception.get("law_id") != "NRS-484B-270-3" or
            not exception.get("authoritative_clause") or
            not exception.get("reviewer") or
            exception.get("status") != case["requested_subsection_3_exception_status"]):
        raise ValueError("independent subsection 3 source does not match exact case")
    if (vehicle.get("source_kind") != "original_reviewed" or
            vehicle.get("vehicle_type") != "motor_vehicle" or
            not vehicle.get("blueprint_id") or not vehicle.get("driver_identity_source")):
        raise ValueError("source-reviewed motor vehicle and driver required")
    route = construct(site_path, route_candidate_id,
                      case["requested_cycle_lane_intersection_overlap"])
    return {"format": "cycle-lane-native-plan-v1", "case_id": case_id,
            "map_id": site["map_id"], "route": route["route_waypoints"],
            "route_candidate_id": route_candidate_id,
            "vehicle_blueprint_id": vehicle["blueprint_id"],
            "site_sha256": site_sha256, "subsection_3_sha256": exception_sha256,
            "vehicle_sha256": vehicle_sha256,
            "capture_profile": {"duration_s": 45, "hz": 20, "views": list(VIEWS),
                                "controller_policy": "cycle-lane-pure-pursuit-v1"},
            "engineering_speed_mps": 5.0,
            "legal_verdict": None, "physical_acceptance_claimed": False}


def control(position_xy, yaw_rad: float, speed_mps: float, route: list,
            target_speed_mps: float = 5.0) -> dict:
    """Pure pursuit at a modest engineering speed; no legal speed claim."""
    if (len(route) < 2 or not all(math.isfinite(v) for v in
            (*position_xy, yaw_rad, speed_mps, target_speed_mps)) or
            target_speed_mps <= 0 or speed_mps < 0):
        raise ValueError("finite route and motion state required")
    x, y = position_xy
    points = [tuple(point) for point in route]
    if any(len(point) != 2 or any(not math.isfinite(v) for v in point) for point in points):
        raise ValueError("finite two-dimensional route required")
    lookahead = max(2.0, min(6.0, 2.0 + speed_mps * 0.5))
    nearest = min(range(len(points)), key=lambda i: math.hypot(points[i][0] - x,
                                                                 points[i][1] - y))
    target = points[-1]
    for point in points[nearest + 1:]:
        if math.hypot(point[0] - x, point[1] - y) >= lookahead:
            target = point
            break
    heading = math.atan2(target[1] - y, target[0] - x)
    error = (heading - yaw_rad + math.pi) % (2 * math.pi) - math.pi
    steer = max(-1.0, min(1.0, 1.25 * error))
    remaining = math.hypot(points[-1][0] - x, points[-1][1] - y)
    if remaining < 0.7:
        return {"throttle": 0.0, "steer": steer, "brake": 1.0,
                "route_complete": True}
    speed_error = target_speed_mps - speed_mps
    return {"throttle": max(0.0, min(0.45, 0.16 * speed_error)),
            "steer": steer, "brake": max(0.0, min(0.5, -0.12 * speed_error)),
            "route_complete": False}
