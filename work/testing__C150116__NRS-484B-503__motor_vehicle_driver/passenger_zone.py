"""C150116 passenger curb zone construction and source-bound saved measurements.

Adapters provide map, sign, clock and CARLA primitives at execution time. This
module never imports CARLA and never treats requested conduct as observed conduct.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import hypot, isfinite
from typing import Mapping
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Case:
    name: str
    conduct: str
    passenger_action: str
    release_delay_s: float
    hours: str = "effective"
    zone_boundary_offset_m: float | None = None
    civil_clock_offset_min: float | None = None


CASES = (
    Case("stop_no_passenger", "stop", "none", 0),
    Case("stand_no_passenger", "stand", "none", 0),
    Case("park_no_passenger", "park", "none", 0),
    Case("load_prompt", "stop", "load", 1),
    Case("unload_prompt", "stop", "unload", 1),
    Case("load_delayed", "stop", "load", 12),
    Case("park_outside_hours", "park", "none", 0, "ineffective"),
    Case("zone_marking-0000", "park", "none", 0, "effective", -0.5),
    Case("zone_marking-0001", "park", "none", 0, "effective", 0.5),
    Case("zone_marking-0002", "park", "none", 0, "effective", 0.0),
    Case("regulation_hours-0000", "park", "none", 0, "source_readback", None, -30.0),
    Case("regulation_hours-0001", "park", "none", 0, "source_readback", None, 30.0),
    Case("regulation_hours-0002", "park", "none", 0, "source_readback", None, 0.0),
    Case("expeditious-0000", "stop", "load", 1, "effective"),
    Case("expeditious-0001", "stop", "load", 12, "effective"),
    Case("expeditious-0002", "stop", "load", 6.5, "effective"),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def signed_boundary_distance(point, polygon):
    px, py = point[:2]
    distances = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        scale = dx * dx + dy * dy
        require(scale > 0, "zero-length marked-zone boundary edge")
        t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / scale))
        distances.append(hypot(px - (a[0] + t * dx), py - (a[1] + t * dy)))
    distance = min(distances)
    return distance if inside_polygon([px, py], polygon) else -distance


def validate_site(site: Mapping, case: Case) -> None:
    require(case in CASES, "unknown case")
    require(site.get("cell_id") == "C150116" and site.get("layout") == "one_way_road", "wrong cell or layout")
    road = site.get("road", {})
    require(road.get("source_sha256") and road.get("one_way_readback") is True, "one-way road source missing")
    require(len(road.get("approach_waypoints", [])) >= 2, "approach route missing")
    zone = site.get("zone", {})
    require(zone.get("marking_source_sha256") and zone.get("boundary_source_sha256"), "marked zone source missing")
    require(zone.get("designation") == "passenger_curb_loading" and zone.get("curb_adjacency_source_sha256"), "passenger curb designation missing")
    polygon = zone.get("polygon_xy", [])
    require(len(polygon) >= 3 and all(len(p) == 2 and all(isinstance(x, (int, float)) and isfinite(x) for x in p) for p in polygon), "zone polygon missing")
    require(zone.get("parking_pose") and zone.get("parking_pose_source_sha256"), "parking pose source missing")
    if case.zone_boundary_offset_m is not None:
        bounds = zone.get("feasible_boundary_offsets_m")
        require(zone.get("boundary_offset_source_sha256") and isinstance(bounds, list) and len(bounds) == 2
                and all(type(value) in (int, float) and isfinite(value) for value in bounds)
                and bounds[0] <= case.zone_boundary_offset_m <= bounds[1],
                "reviewed marked-zone boundary offset feasibility missing")
        measured = signed_boundary_distance(zone["parking_pose"], polygon)
        require(abs(measured - case.zone_boundary_offset_m) <= 0.05,
                "surveyed parking pose differs from requested marked-zone offset")
    clock = site.get("clock", {})
    require(clock.get("civil_time_iso") and clock.get("timezone") and clock.get("source_sha256"), "civil clock source missing")
    dt = datetime.fromisoformat(clock["civil_time_iso"])
    require(dt.tzinfo is not None, "civil time must include offset")
    require(dt.utcoffset() == dt.astimezone(ZoneInfo(clock["timezone"])).utcoffset(), "civil timezone mismatch")
    regulations = site.get("regulations", {})
    require(regulations.get("source_sha256") and regulations.get("jurisdiction") and regulations.get("effective_hours_source_sha256"), "applicable regulations missing")
    effective = regulations.get("effective_at_civil_time")
    require(type(effective) is bool, "original effective-hours readback missing")
    if case.hours != "source_readback":
        require(effective is (case.hours == "effective"), "hours readback differs from case")
    if case.civil_clock_offset_min is not None:
        boundary = clock.get("effective_boundary_civil_iso")
        require(clock.get("effective_boundary_source_sha256") and boundary,
                "reviewed effective-hours boundary and civil clock source missing")
        boundary_dt = datetime.fromisoformat(boundary)
        require(boundary_dt.tzinfo is not None and
                abs((dt - boundary_dt).total_seconds() / 60 - case.civil_clock_offset_min) <= 0.01,
                "sourced civil clock differs from requested engineering offset")
    if case.name.startswith("expeditious-"):
        require(site.get("passenger_event_source_sha256"),
                "original passenger-event source missing")
    require(site.get("vehicle_blueprint") and site.get("vehicle_blueprint_source_sha256"), "vehicle source missing")
    require(site.get("passenger_blueprint") and site.get("passenger_blueprint_source_sha256"), "passenger source missing")


def build_case(adapter, site: Mapping, case: Case):
    """Spawn vehicle and passenger at sourced zone, then command one conduct path."""
    validate_site(site, case)
    owned = []
    try:
        ego = adapter.spawn_vehicle(site["road"]["approach_waypoints"][0], blueprint=site["vehicle_blueprint"], role="ego")
        require(ego is not None, "ego spawn failed")
        owned.append(ego)
        passenger = adapter.spawn_passenger(site["zone"]["passenger_anchor"], blueprint=site["passenger_blueprint"])
        require(passenger is not None, "passenger spawn failed")
        owned.append(passenger)
        adapter.set_route(ego, site["road"]["approach_waypoints"], site["zone"]["parking_pose"])
        adapter.set_conduct(ego, case.conduct)
        adapter.set_passenger_action(passenger, ego, case.passenger_action, release_delay_s=case.release_delay_s)
        return {"case": case.name, "ego": ego, "passenger": passenger, "owned": tuple(owned)}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def inside_polygon(point, polygon):
    """Ray cast; boundary points need later physical review."""
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def measure_history(rows: list[Mapping], case: Case, site: Mapping) -> dict:
    """Measure original 20 Hz vehicle/passenger events without a legal label."""
    validate_site(site, case)
    require(len(rows) == 900, "900 original frames required")
    first = rows[0].get("original_frame")
    require(type(first) is int, "original frame missing")
    halted, in_zone, passenger_events, all_events = [], [], [], []
    halted_positions = []
    previous_time = None
    fixed = None
    for index, row in enumerate(rows):
        require(row.get("case_id") == case.name and row.get("original_frame") == first + index, "case/frame join mismatch")
        elapsed = row.get("elapsed_s")
        require(isinstance(elapsed, (int, float)) and isfinite(elapsed) and (previous_time is None or elapsed > previous_time), "elapsed time missing or discontinuous")
        previous_time = elapsed
        ids = tuple(row.get(key) for key in ("ego_id", "passenger_id", "map_sha256", "zone_source_sha256", "regulations_source_sha256", "clock_source_sha256"))
        require(all(ids), "original identity/source missing")
        if fixed is None:
            fixed = ids
        require(ids == fixed, "fixed source or actor changed")
        require(row.get("source_sha256") and row.get("control_source_sha256"), "original packet source missing")
        center = row.get("ego_center_xy")
        speed = row.get("ego_speed_mps")
        require(isinstance(center, list) and len(center) == 2 and all(isinstance(v, (int, float)) and isfinite(v) for v in center), "ego position missing")
        require(isinstance(speed, (int, float)) and isfinite(speed) and speed >= 0, "ego speed missing")
        # Engineering zero-speed tolerance only identifies a measured halt.
        if speed <= 0.05:
            halted.append(index)
            halted_positions.append(center)
            if inside_polygon(center, site["zone"]["polygon_xy"]):
                in_zone.append(index)
        event = row.get("passenger_event")
        require(event in (None, "boarding_started", "boarding_completed", "alighting_started", "alighting_completed"), "passenger event invalid")
        if event:
            require(row.get("passenger_event_source_sha256"), "passenger event source missing")
            passenger_events.append({"frame": first + index, "event": event, "time_s": elapsed})
        all_events.append(event)
    first_halt_time = rows[halted[0]]["elapsed_s"] if halted else None
    event_delay = (passenger_events[0]["time_s"] - first_halt_time
                   if first_halt_time is not None and passenger_events else None)
    civil_offset = None
    if case.civil_clock_offset_min is not None:
        clock = site["clock"]
        civil_offset = (datetime.fromisoformat(clock["civil_time_iso"]) -
                        datetime.fromisoformat(clock["effective_boundary_civil_iso"])).total_seconds() / 60
    return {"case_id": case.name, "first_original_frame": first, "last_original_frame": first + 899,
            "frame_count": 900, "halted_frame_count": len(halted), "in_zone_halted_frame_count": len(in_zone),
            "first_in_zone_halt_frame": first + in_zone[0] if in_zone else None,
            "last_in_zone_halt_frame": first + in_zone[-1] if in_zone else None,
            "passenger_events": passenger_events, "passenger_event_count": len(passenger_events),
            "regulations_effective": site["regulations"]["effective_at_civil_time"],
            "zone_boundary_signed_distance_m": signed_boundary_distance(halted_positions[0], site["zone"]["polygon_xy"]) if halted_positions else None,
            "civil_boundary_offset_min": civil_offset,
            "passenger_event_delay_s": event_delay,
            "source_ids": fixed, "legal_judgment": None, "physical_visibility_verified": False}


def audit_pair(left: Mapping, right: Mapping, difference: str) -> dict:
    require(left.get("case_id") != right.get("case_id"), "duplicate comparison case")
    for side in (left, right):
        require(side.get("frame_count") == 900 and side.get("original_history_sha256"), "comparison history missing")
        require(side.get("site_sha256") and side.get("camera_plan_sha256") and side.get("zone_source_sha256"), "fixed comparison source missing")
    for key in ("site_sha256", "camera_plan_sha256", "zone_source_sha256", "vehicle_blueprint", "passenger_blueprint"):
        require(left.get(key) and left.get(key) == right.get(key), f"fixed comparison condition changed: {key}")
    require(difference in ("conduct", "passenger_action", "release_delay_s", "regulations_effective"), "unsupported comparison difference")
    require(left.get(difference) != right.get(difference), "deliberate difference absent")
    if difference != "regulations_effective":
        require(left.get("regulations_effective") is True and right.get("regulations_effective") is True, "comparison hours changed")
    return {"left": left["case_id"], "right": right["case_id"], "difference": difference, "legal_judgment": None}
