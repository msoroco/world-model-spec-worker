"""Source-gated controlled-access exit construction and original-frame measurements.

The adapter is supplied by the local simulator. This module imports no CARLA code.
Measurements describe conduct and proximity; they never decide immediate hazard
or reasonable safety under NRS 484B.263.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    policy: str
    approaching_count: int
    approach_headway_s: float


CASES = (
    Case("exit_yield_first", "yield_until_clear", 1, 3.0),
    Case("exit_proceed_first", "proceed_before_clear", 1, 3.0),
    Case("exit_yield_second", "yield_until_clear", 2, 3.0),
    Case("exit_proceed_between", "proceed_between_vehicles", 2, 3.0),
    Case("exit_distant_approach", "yield_until_clear", 1, 9.0),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite_number(value, name):
    require(type(value) in (float, int) and isfinite(value), f"{name} missing")
    return float(value)


def validate_site(site: Mapping, case: Case) -> None:
    require(case in CASES, "unknown case")
    require(site.get("cell_id") == "C228302" and site.get("layout") == "road" and site.get("maneuver") == "exit_road", "wrong cell")
    road = site.get("road", {})
    for key in ("map_sha256", "public_dedication_source_sha256", "public_access_source_sha256",
                "restricted_access_authority_source_sha256", "restricted_access_determination_source_sha256",
                "highway_boundary_source_sha256", "exit_connection_source_sha256", "route_source_sha256"):
        require(road.get(key), f"road source missing: {key}")
    require(road.get("controlled_access_readback") is True, "controlled-access readback absent")
    require(road.get("exit_connection_readback") is True, "exit connection readback absent")
    require(len(road.get("exit_waypoints", [])) >= 3, "exit route missing")
    require(len(road.get("highway_approach_waypoints", [])) >= 3, "highway approach missing")
    require(road.get("exit_merge_polygon_xy") and len(road["exit_merge_polygon_xy"]) >= 3, "exit interaction polygon missing")
    require(site.get("ego_blueprint") and site.get("ego_blueprint_source_sha256"), "ego source missing")
    require(site.get("approach_blueprint") and site.get("approach_blueprint_source_sha256"), "approaching vehicle source missing")
    require(site.get("driver_control_source_sha256"), "driver control source missing")
    require(case.approaching_count in (1, 2) and case.approach_headway_s > 0, "invalid approach design")


def build_case(adapter, site: Mapping, case: Case):
    """Create a real exit route and one or two highway vehicles with rollback."""
    validate_site(site, case)
    road = site["road"]
    require(adapter.read_map_hash() == road["map_sha256"], "map readback mismatch")
    require(adapter.read_controlled_access(road) is True, "controlled-access runtime readback mismatch")
    require(adapter.read_exit_connection(road) is True, "exit connection runtime readback mismatch")
    owned = []
    try:
        ego = adapter.spawn_vehicle(road["exit_waypoints"][0], blueprint=site["ego_blueprint"], role="ego")
        require(ego is not None, "ego spawn failed")
        owned.append(ego)
        approaching = []
        for index in range(case.approaching_count):
            vehicle = adapter.spawn_vehicle(road["highway_approach_waypoints"][index], blueprint=site["approach_blueprint"], role="approaching")
            require(vehicle is not None, "approaching vehicle spawn failed")
            approaching.append(vehicle)
            owned.append(vehicle)
            adapter.set_route(vehicle, road["highway_approach_waypoints"], role="approaching")
            adapter.set_headway(vehicle, case.approach_headway_s + index * 2)
        adapter.set_route(ego, road["exit_waypoints"], role="ego")
        adapter.set_exit_policy(ego, case.policy, approaching)
        return {"case_id": case.name, "ego": ego, "approaching": tuple(approaching), "owned": tuple(owned)}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def _inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def measure_history(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    """Measure all relevant vehicles over the complete original 20 Hz history."""
    validate_site(site, case)
    require(len(rows) == 900, "900 original frames required")
    first = rows[0].get("original_frame")
    require(type(first) is int, "original frame missing")
    fixed = None
    entry, waits, approach_ranges = [], [], {}
    expected_actor_ids = None
    for index, row in enumerate(rows):
        require(row.get("case_id") == case.name and row.get("original_frame") == first + index, "case/frame join mismatch")
        elapsed = _finite_number(row.get("elapsed_s"), "elapsed time")
        require(abs(elapsed - index * 0.05) <= 0.001, "20 Hz original time mismatch")
        identities = tuple(row.get(key) for key in ("ego_id", "map_sha256", "site_sha256", "camera_plan_sha256", "road_authority_source_sha256"))
        require(all(identities), "fixed identity/source missing")
        if fixed is None:
            fixed = identities
        require(identities == fixed, "fixed source or actor changed")
        require(row.get("source_sha256") and row.get("control_source_sha256"), "original packet source missing")
        point = row.get("ego_center_xy")
        require(type(point) is list and len(point) == 2, "ego original position missing")
        _finite_number(point[0], "ego x")
        _finite_number(point[1], "ego y")
        speed = _finite_number(row.get("ego_speed_mps"), "ego speed")
        require(speed >= 0, "negative ego speed")
        inside = _inside(point, site["road"]["exit_merge_polygon_xy"])
        if inside:
            entry.append(first + index)
        if not inside and speed <= 0.05:
            waits.append(first + index)
        vehicles = row.get("approaching_vehicles")
        require(type(vehicles) is list and len(vehicles) == case.approaching_count, "all approaching vehicles required")
        seen = set()
        for vehicle in vehicles:
            identifier = vehicle.get("actor_id")
            require(identifier is not None and identifier not in seen, "approaching actor identity missing or duplicated")
            seen.add(identifier)
            require(vehicle.get("source_sha256") and vehicle.get("highway_occupancy_source_sha256"), "approaching original source missing")
            require(vehicle.get("on_highway") is True, "approaching highway occupancy missing")
            distance = _finite_number(vehicle.get("range_to_interaction_m"), "approach range")
            require(distance >= 0, "negative approach range")
            speed_other = _finite_number(vehicle.get("speed_mps"), "approach speed")
            require(speed_other >= 0, "negative approach speed")
            approach_ranges.setdefault(identifier, []).append(distance)
        if expected_actor_ids is None:
            expected_actor_ids = seen
        require(seen == expected_actor_ids, "approaching identity changed")
        require(len(approach_ranges) == case.approaching_count, "approaching identity changed")
    require(entry, "ego never entered exit interaction")
    return {"case_id": case.name, "frame_count": 900, "first_original_frame": first,
            "last_original_frame": first + 899, "first_entry_frame": entry[0],
            "last_entry_frame": entry[-1], "pre_entry_wait_frames": len([x for x in waits if x < entry[0]]),
            "approaching_actor_ids": sorted(approach_ranges),
            "minimum_approach_range_m": {str(k): min(v) for k, v in approach_ranges.items()},
            "fixed_source_ids": fixed, "immediate_hazard_judgment": None,
            "reasonable_safety_judgment": None, "physical_visibility_verified": False}


def audit_comparison(left: Mapping, right: Mapping, difference: str) -> dict:
    require(left.get("case_id") != right.get("case_id"), "duplicate case")
    for record in (left, right):
        require(record.get("frame_count") == 900 and record.get("original_history_sha256"), "sealed original history missing")
        for key in ("map_sha256", "site_sha256", "camera_plan_sha256", "exit_route_sha256", "approach_route_sha256", "blueprints_sha256"):
            require(record.get(key), f"fixed source missing: {key}")
    for key in ("map_sha256", "site_sha256", "camera_plan_sha256", "exit_route_sha256", "approach_route_sha256", "blueprints_sha256"):
        require(left[key] == right[key], f"fixed comparison condition changed: {key}")
    require(difference in ("policy", "approaching_count", "approach_headway_s"), "unsupported difference")
    require(left.get(difference) != right.get(difference), "declared difference absent")
    for key in ("policy", "approaching_count", "approach_headway_s"):
        if key != difference:
            require(left.get(key) == right.get(key), f"undeclared difference: {key}")
    return {"left": left["case_id"], "right": right["case_id"], "difference": difference, "legal_judgment": None}
