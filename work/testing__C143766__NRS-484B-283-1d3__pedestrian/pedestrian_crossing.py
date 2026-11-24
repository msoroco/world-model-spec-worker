"""Source-gated pedestrian crossing plans and original signal/arrival measurement.

An observed Walk-phase entry is not a legal finding under NRS 484B.283(1)(d)(1).
The referenced exceptions and the status of each place of safety stay unresolved.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    entry_phase: str
    destination: str
    arrival_phase: str
    countdown: bool


CASES = (
    Case("walk_entry_sidewalk_before", "walk", "sidewalk", "flashing", False),
    Case("walk_entry_sidewalk_after", "walk", "sidewalk", "steady", False),
    Case("flashing_new_entry", "flashing", "sidewalk", "flashing", False),
    Case("walk_entry_curb_before", "walk", "curb", "flashing", False),
    Case("walk_entry_safety_zone_before", "walk", "safety_zone", "flashing", False),
    Case("walk_entry_other_place_before", "walk", "other_place", "flashing", False),
    Case("countdown_present", "walk", "sidewalk", "flashing", True),
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def point(value, name: str) -> tuple[float, float]:
    require(isinstance(value, (list, tuple)) and len(value) == 2 and
            all(type(x) in (int, float) and isfinite(x) for x in value),
            name + " coordinate missing")
    return float(value[0]), float(value[1])


def near(a, b, distance=.5) -> bool:
    ax, ay = point(a, "first point")
    bx, by = point(b, "second point")
    return hypot(ax - bx, ay - by) <= distance


def in_polygon(value, polygon) -> bool:
    x, y = point(value, "original pedestrian")
    inside = False
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def validate_site(site: Mapping) -> None:
    require(site.get("cell_id") == "C143766" and site.get("actor") == "pedestrian",
            "wrong trail-connected pedestrian cell")
    for field in ("trail_source_sha256", "highway_source_sha256", "crossing_source_sha256",
                  "sidewalk_source_sha256", "signal_source_sha256", "signal_facing_source_sha256"):
        require(bool(site.get(field)), "original site source missing: " + field)
    require(site.get("signal_facing_pedestrian") is True,
            "pedestrian signal does not face crossing")
    trail = site.get("trail_route_xy")
    crossing = site.get("crossing_route_xy")
    require(isinstance(trail, list) and len(trail) >= 2 and
            isinstance(crossing, list) and len(crossing) >= 2,
            "trail and crossing routes missing")
    for route in (trail, crossing):
        for coordinate in route:
            point(coordinate, "route waypoint")
    require(near(trail[-1], crossing[0]), "trail does not connect to crossing")
    polygon = site.get("highway_polygon_xy")
    require(isinstance(polygon, list) and len(polygon) >= 3,
            "original highway polygon missing")
    for coordinate in polygon:
        point(coordinate, "highway polygon")
    require(not in_polygon(trail[0], polygon) and
            any(in_polygon(coordinate, polygon) for coordinate in crossing[1:-1]),
            "route does not traverse sourced highway")
    destinations = site.get("destination_routes", {})
    for kind in ("curb", "sidewalk", "safety_zone", "other_place"):
        route = destinations.get(kind, {})
        waypoints = route.get("waypoints_xy")
        require(route.get("source_sha256") and isinstance(waypoints, list) and
                len(waypoints) >= 2, "sourced destination route missing: " + kind)
        for coordinate in waypoints:
            point(coordinate, kind + " waypoint")
        require(near(crossing[-1], waypoints[0]),
                "crossing does not connect to " + kind)
    require(site.get("safety_zone_provided_source_sha256") and
            site.get("other_place_safety_review_sha256"),
            "safety-zone or other-place source review missing")


def construct(adapter, site: Mapping, case: Case) -> dict:
    """Request a sourced route and signal schedule; do not claim actual display."""
    validate_site(site)
    require(case in CASES, "unknown exact pedestrian case")
    owned = []
    try:
        ped = adapter.spawn_pedestrian(site["trail_route_xy"][0])
        require(ped is not None, "pedestrian spawn failed")
        owned.append(ped)
        adapter.request_signal_schedule(walk_until_s=5, flashing_until_s=15,
                                        countdown_during_flashing=case.countdown)
        route = (site["trail_route_xy"] + site["crossing_route_xy"][1:] +
                 site["destination_routes"][case.destination]["waypoints_xy"][1:])
        adapter.set_pedestrian_route(ped, route, requested_entry_s=4 if case.entry_phase == "walk" else 6,
                                     requested_arrival_s=16 if case.arrival_phase == "steady" else 14)
        return {"case_id": case.case_id, "pedestrian": ped, "owned": tuple(owned),
                "route_xy": route, "destination": case.destination,
                "entry_lawfulness": "unresolved", "exception_applicability": "unresolved",
                "legal_judgment": None}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    """Join original 20 Hz signal and pedestrian positions; retain legal unknowns."""
    validate_site(site)
    require(case in CASES and len(rows) == 900, "exact case or original 900 frames missing")
    first = rows[0].get("original_frame")
    require(type(first) is int, "original frame identity missing")
    identity = None
    entry = arrival = steady = None
    flashing_seen = walk_seen = False
    previous_phase = None
    target = site["destination_routes"][case.destination]["waypoints_xy"][-1]
    for i, row in enumerate(rows):
        require(row.get("original_frame") == first + i and
                type(row.get("time_s")) in (int, float) and
                abs(row["time_s"] - rows[0]["time_s"] - i / 20) <= .005,
                "original frame/time join invalid")
        for name in ("source_sha256", "signal_readback_sha256", "pedestrian_pose_sha256"):
            require(bool(row.get(name)), "original source missing: " + name)
        require(row.get("site_source_sha256") == site["signal_source_sha256"] and
                row.get("facing_source_sha256") == site["signal_facing_source_sha256"],
                "original signal site changed")
        ped_id = row.get("pedestrian_id")
        require(bool(ped_id), "original pedestrian identity missing")
        if identity is None:
            identity = ped_id
        require(ped_id == identity, "original pedestrian identity changed")
        phase = row.get("signal_phase")
        require(phase in ("walk", "flashing", "steady"), "original signal phase missing")
        require(previous_phase is None or
                (previous_phase, phase) in (("walk", "walk"), ("walk", "flashing"),
                                            ("flashing", "flashing"), ("flashing", "steady"),
                                            ("steady", "steady")),
                "original signal transition invalid")
        previous_phase = phase
        walk_seen |= phase == "walk"
        flashing_seen |= phase == "flashing"
        if phase == "steady" and steady is None:
            steady = row["original_frame"]
        countdown = row.get("countdown_visible")
        require(type(countdown) is bool, "original countdown readback missing")
        if phase == "flashing":
            require(countdown == case.countdown, "flashing countdown differs from case")
        if in_polygon(row.get("pedestrian_xy"), site["highway_polygon_xy"]) and entry is None:
            entry = (row["original_frame"], phase)
        if near(row.get("pedestrian_xy"), target) and arrival is None:
            arrival = (row["original_frame"], phase)
    require(walk_seen and flashing_seen and steady is not None,
            "original Walk/flashing/steady history incomplete")
    require(entry is not None and entry[1] == case.entry_phase,
            "original entry phase differs from case")
    require(arrival is not None and arrival[1] == case.arrival_phase,
            "original destination arrival differs from case")
    require(entry[0] < arrival[0], "arrival precedes highway entry")
    return {"case_id": case.case_id, "first_original_frame": first,
            "last_original_frame": first + 899, "frame_count": 900,
            "entry_original_frame": entry[0], "entry_phase": entry[1],
            "arrival_original_frame": arrival[0], "arrival_phase": arrival[1],
            "steady_original_frame": steady, "destination": case.destination,
            "countdown_during_flashing": case.countdown,
            "prior_entry_lawfulness": "unresolved", "exception_applicability": "unresolved",
            "legal_judgment": None}
