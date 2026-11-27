"""Source-gated freight curb construction and original-frame measurements.

The local adapter supplies reviewed site data and CARLA primitives. Requested
conduct never substitutes for observed activity or a legal finding.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import hypot, isfinite
from typing import Mapping
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Case:
    name: str
    conduct: str
    material_action: str
    activity_delay_s: float
    hours: str = "effective"
    passenger_action: str = "none"
    freight_arrival: str = "none"
    zone_boundary_offset_m: float | None = None
    civil_clock_offset_min: float | None = None
    passenger_dwell_s: float | None = None
    freight_entry_headway_s: float | None = None


CASES = (
    Case("stop_no_material", "stop", "none", 0),
    Case("stand_no_material", "stand", "none", 0),
    Case("park_no_material", "park", "none", 0),
    Case("pickup_load_prompt", "stop", "pickup_load", 1),
    Case("unload_deliver_prompt", "stop", "unload_deliver", 1),
    Case("pickup_load_delayed", "stop", "pickup_load", 12),
    Case("park_outside_hours", "park", "none", 0, "ineffective"),
    Case("passenger_board_clear", "stop", "none", 0, passenger_action="board"),
    Case("passenger_alight_clear", "stop", "none", 0, passenger_action="alight"),
    Case("passenger_board_waiting_freight", "stop", "none", 0, passenger_action="board", freight_arrival="waiting"),
    Case("passenger_board_about_to_enter", "stop", "none", 0, passenger_action="board", freight_arrival="about_to_enter"),
    Case("passenger_stop_no_activity", "stop", "none", 0, passenger_action="none", freight_arrival="waiting"),
    Case("sweep_material_delay-0000", "stop", "pickup_load", 1),
    Case("sweep_material_delay-0001", "stop", "pickup_load", 12),
    Case("sweep_material_delay-0002", "stop", "pickup_load", 6.5),
    Case("sweep_marked_boundary-0000", "stop", "none", 0, zone_boundary_offset_m=-0.5),
    Case("sweep_marked_boundary-0001", "stop", "none", 0, zone_boundary_offset_m=0.5),
    Case("sweep_marked_boundary-0002", "stop", "none", 0, zone_boundary_offset_m=0),
    Case("sweep_effective_hours-0000", "park", "none", 0, "ineffective", civil_clock_offset_min=-30),
    Case("sweep_effective_hours-0001", "park", "none", 0, "effective", civil_clock_offset_min=30),
    Case("sweep_effective_hours-0002", "park", "none", 0, "effective", civil_clock_offset_min=0),
    Case("sweep_passenger_dwell-0000", "stop", "none", 0, passenger_action="board", passenger_dwell_s=2),
    Case("sweep_passenger_dwell-0001", "stop", "none", 0, passenger_action="board", passenger_dwell_s=10),
    Case("sweep_passenger_dwell-0002", "stop", "none", 0, passenger_action="board", passenger_dwell_s=6),
    Case("sweep_freight_headway-0000", "stop", "none", 0, passenger_action="board", freight_arrival="about_to_enter", freight_entry_headway_s=0),
    Case("sweep_freight_headway-0001", "stop", "none", 0, passenger_action="board", freight_arrival="about_to_enter", freight_entry_headway_s=4),
    Case("sweep_freight_headway-0002", "stop", "none", 0, passenger_action="board", freight_arrival="about_to_enter", freight_entry_headway_s=2),
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def inside_polygon(point, polygon) -> bool:
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            cross_x = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            if x < cross_x:
                inside = not inside
    return inside


def distance_to_boundary(point, polygon) -> float:
    px, py = point
    distances = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        scale = dx * dx + dy * dy
        require(scale > 0, "zero-length freight-zone edge")
        t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / scale))
        distances.append(hypot(px - (a[0] + t * dx), py - (a[1] + t * dy)))
    d = min(distances)
    return d if inside_polygon(point, polygon) else -d


def validate_site(site: Mapping, case: Case) -> None:
    require(case in CASES, "unknown case")
    require(site.get("cell_id") == "C386226" and site.get("layout") == "one_way_road", "wrong cell or layout")
    road = site.get("road", {})
    require(road.get("source_sha256") and road.get("one_way_readback") is True, "one-way source missing")
    require(len(road.get("approach_waypoints", [])) >= 2, "approach route missing")
    zone = site.get("zone", {})
    require(zone.get("designation") == "freight_curb_loading", "freight designation missing")
    for key in ("marking_source_sha256", "boundary_source_sha256", "curb_adjacency_source_sha256", "parking_pose_source_sha256"):
        require(zone.get(key), "freight zone source missing: " + key)
    polygon = zone.get("polygon_xy", [])
    require(len(polygon) >= 3 and all(len(p) == 2 and all(type(x) in (int, float) and isfinite(x) for x in p) for p in polygon), "freight polygon missing")
    require(zone.get("parking_pose") and len(zone["parking_pose"]) >= 2, "parking pose missing")
    require(zone.get("materials_anchor") and zone.get("passenger_anchor"), "activity anchors missing")
    require(road.get("freight_entry_waypoint") and road.get("freight_entry_source_sha256"), "freight entry route source missing")
    regulations = site.get("regulations", {})
    for key in ("source_sha256", "effective_hours_source_sha256", "jurisdiction"):
        require(regulations.get(key), "applicable provision source missing: " + key)
    effective = regulations.get("effective_at_civil_time")
    require(type(effective) is bool and effective is (case.hours == "effective"), "effective-hours readback differs from case")
    clock = site.get("clock", {})
    require(clock.get("source_sha256") and clock.get("civil_time_iso") and clock.get("timezone"), "civil clock source missing")
    civil = datetime.fromisoformat(clock["civil_time_iso"])
    require(civil.tzinfo is not None and civil.utcoffset() == civil.astimezone(ZoneInfo(clock["timezone"])).utcoffset(), "civil time zone mismatch")
    require(site.get("vehicle_blueprint") and site.get("vehicle_blueprint_source_sha256"), "ego vehicle source missing")
    require(site.get("driver_responsibility_source_sha256"), "selected driver responsibility source missing")
    require(site.get("materials_inventory") and site.get("materials_inventory_source_sha256"), "materials inventory source missing")
    require(site.get("freight_vehicle_blueprint") and site.get("freight_vehicle_blueprint_source_sha256"), "materials-transport vehicle source missing")
    require(site.get("passenger_blueprint") and site.get("passenger_blueprint_source_sha256"), "passenger source missing")
    require(site.get("activity_controller_source_sha256"), "activity controller source missing")
    require(site.get("traffic_and_official_directions_source_sha256"), "traffic/officer context source missing")
    if case.zone_boundary_offset_m is not None:
        anchor = zone.get("boundary_anchor_xy")
        inward = zone.get("boundary_inward_normal_xy")
        require(zone.get("boundary_anchor_source_sha256") and anchor and inward,
                "reviewed marked-boundary anchor and inward normal missing")
        require(len(anchor) == len(inward) == 2 and all(isfinite(float(v)) for v in anchor + inward),
                "marked-boundary geometry invalid")
        target = [anchor[i] + case.zone_boundary_offset_m * inward[i] for i in (0, 1)]
        require(all(abs(zone["parking_pose"][i] - target[i]) < 0.001 for i in (0, 1)),
                "sweep parking pose differs from sourced marked-boundary offset")
    if case.civil_clock_offset_min is not None:
        boundary = clock.get("effective_boundary_civil_time_iso")
        require(clock.get("effective_boundary_source_sha256") and boundary,
                "reviewed applicable-hours boundary missing")
        require(civil == datetime.fromisoformat(boundary) + timedelta(minutes=case.civil_clock_offset_min),
                "civil clock differs from source-gated engineering offset")
    if case.passenger_dwell_s is not None:
        require(site.get("passenger_dwell_controller_source_sha256") and case.passenger_action != "none",
                "reviewed passenger activity duration source missing")
    if case.freight_entry_headway_s is not None:
        require(road.get("freight_headway_controller_source_sha256") and case.freight_arrival != "none",
                "reviewed freight entry headway source missing")


def build_case(adapter, site: Mapping, case: Case):
    """Spawn source-selected participants and command the chosen activity path."""
    validate_site(site, case)
    owned = []
    try:
        ego = adapter.spawn_vehicle(site["road"]["approach_waypoints"][0], blueprint=site["vehicle_blueprint"], role="ego")
        require(ego is not None, "ego spawn failed")
        owned.append(ego)
        materials = adapter.spawn_materials(site["zone"]["materials_anchor"], inventory=site["materials_inventory"])
        require(materials is not None, "materials spawn failed")
        owned.append(materials)
        passenger = adapter.spawn_passenger(site["zone"]["passenger_anchor"], blueprint=site["passenger_blueprint"])
        require(passenger is not None, "passenger spawn failed")
        owned.append(passenger)
        freight = adapter.spawn_vehicle(site["road"]["freight_entry_waypoint"], blueprint=site["freight_vehicle_blueprint"], role="freight_waiter")
        require(freight is not None, "freight vehicle spawn failed")
        owned.append(freight)
        adapter.set_route(ego, site["road"]["approach_waypoints"], site["zone"]["parking_pose"])
        adapter.set_conduct(ego, case.conduct)
        adapter.set_material_action(materials, ego, case.material_action, delay_s=case.activity_delay_s)
        if case.passenger_dwell_s is None:
            adapter.set_passenger_action(passenger, ego, case.passenger_action)
        else:
            require(callable(getattr(adapter, "set_passenger_dwell", None)), "passenger dwell controller unavailable")
            adapter.set_passenger_dwell(passenger, ego, case.passenger_action, duration_s=case.passenger_dwell_s)
        if case.freight_entry_headway_s is None:
            adapter.set_freight_arrival(freight, case.freight_arrival, site["road"]["freight_entry_waypoint"])
        else:
            require(callable(getattr(adapter, "set_freight_headway", None)), "freight headway controller unavailable")
            adapter.set_freight_headway(freight, case.freight_arrival, site["road"]["freight_entry_waypoint"],
                                        headway_s=case.freight_entry_headway_s)
        return {"case": case.name, "ego": ego, "materials": materials, "passenger": passenger, "freight": freight, "owned": tuple(owned)}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_history(rows: list[Mapping], case: Case, site: Mapping) -> dict:
    """Measure observed original-frame chronology; leave legal judgment open."""
    validate_site(site, case)
    require(len(rows) == 900, "900 original frames required")
    first = rows[0].get("original_frame")
    require(type(first) is int, "first original frame missing")
    last_elapsed = None
    fixed = None
    halted, in_zone, material_events, passenger_events, freight_events = [], [], [], [], []
    freight_positions, blocked_entry_frames = [], []
    positions = []
    for index, row in enumerate(rows):
        require(row.get("case_id") == case.name and row.get("original_frame") == first + index, "case/frame join mismatch")
        elapsed = row.get("elapsed_s")
        require(type(elapsed) in (int, float) and isfinite(elapsed) and (last_elapsed is None or elapsed > last_elapsed), "original time discontinuity")
        last_elapsed = elapsed
        ids = tuple(row.get(k) for k in ("ego_id", "driver_id", "materials_id", "passenger_id", "freight_vehicle_id", "map_sha256", "zone_source_sha256", "regulations_source_sha256", "clock_source_sha256", "traffic_and_official_directions_source_sha256"))
        require(all(ids), "participant or site source missing")
        if fixed is None:
            fixed = ids
        require(ids == fixed, "participant or site source changed")
        require(row.get("source_sha256") and row.get("control_source_sha256"), "original packet source missing")
        center, speed = row.get("ego_center_xy"), row.get("ego_speed_mps")
        require(isinstance(center, list) and len(center) == 2 and all(type(v) in (int, float) and isfinite(v) for v in center), "ego pose missing")
        require(type(speed) in (int, float) and isfinite(speed) and speed >= 0, "ego speed missing")
        if speed <= 0.05:
            halted.append(first + index)
            positions.append(center)
            if inside_polygon(center, site["zone"]["polygon_xy"]):
                in_zone.append(first + index)
        freight_pose = row.get("freight_center_xy")
        require(isinstance(freight_pose, list) and len(freight_pose) == 2 and all(type(v) in (int, float) and isfinite(v) for v in freight_pose), "freight vehicle pose missing")
        freight_positions.append(freight_pose)
        blocked = row.get("freight_entry_blocked")
        require(type(blocked) is bool, "freight entry obstruction readback missing")
        if blocked:
            require(row.get("freight_entry_blocked_source_sha256"), "freight obstruction source missing")
            blocked_entry_frames.append(first + index)
        for channel, allowed, target in (
            ("material_event", {"pickup_started", "pickup_completed", "loading_started", "loading_completed", "unloading_started", "unloading_completed", "delivery_started", "delivery_completed"}, material_events),
            ("passenger_event", {"boarding_started", "boarding_completed", "alighting_started", "alighting_completed"}, passenger_events),
            ("freight_event", {"waiting_to_enter", "about_to_enter", "entered_zone", "departed_zone"}, freight_events),
        ):
            event = row.get(channel)
            require(event is None or event in allowed, channel + " invalid")
            if event is not None:
                require(row.get(channel + "_source_sha256"), channel + " source missing")
                target.append({"frame": first + index, "time_s": elapsed, "event": event})
    first_halt = halted[0] if halted else None
    activity_start = material_events[0]["frame"] if material_events else None
    passenger_start = next((event["time_s"] for event in passenger_events if event["event"] == "boarding_started"), None)
    passenger_finish = next((event["time_s"] for event in passenger_events if event["event"] == "boarding_completed"), None)
    freight_approach = next((event["time_s"] for event in freight_events if event["event"] == "about_to_enter"), None)
    return {
        "case_id": case.name, "first_original_frame": first, "last_original_frame": first + 899,
        "frame_count": 900, "halted_frame_count": len(halted),
        "in_zone_halted_frame_count": len(in_zone), "first_in_zone_halt_frame": in_zone[0] if in_zone else None,
        "first_material_event_frame": activity_start, "material_events": material_events,
        "passenger_events": passenger_events, "freight_events": freight_events,
        "freight_vehicle_positions_xy": freight_positions,
        "freight_entry_blocked_frames": blocked_entry_frames,
        "halt_to_material_event_s": ((activity_start - first_halt) / 20 if activity_start is not None and first_halt is not None else None),
        "observed_passenger_dwell_s": (passenger_finish - passenger_start if passenger_start is not None and passenger_finish is not None else None),
        "observed_freight_entry_headway_s": (freight_approach - (first_halt - first) / 20 if freight_approach is not None and first_halt is not None else None),
        "civil_boundary_offset_min": (
            (datetime.fromisoformat(site["clock"]["civil_time_iso"]) -
             datetime.fromisoformat(site["clock"]["effective_boundary_civil_time_iso"])).total_seconds() / 60
            if case.civil_clock_offset_min is not None else None),
        "halt_positions_xy": positions, "marked_zone_signed_distance_m": [distance_to_boundary(p, site["zone"]["polygon_xy"]) for p in positions],
        "civil_time_iso": site["clock"]["civil_time_iso"], "timezone": site["clock"]["timezone"],
        "provisions_effective": site["regulations"]["effective_at_civil_time"],
        "source_bindings": dict(zip(("ego_id", "driver_id", "materials_id", "passenger_id", "freight_vehicle_id", "map_sha256", "zone_source_sha256", "regulations_source_sha256", "clock_source_sha256", "traffic_and_official_directions_source_sha256"), fixed)),
        "legal_judgment": "unresolved",
    }
