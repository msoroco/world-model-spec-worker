"""Source-bound construction and measurement for NRS 484B.283(1)(d)(2).

The zero boundary is statutory. Requested timing is an engineering target; only
the original same-frame signal and pedestrian observations establish timing.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    signal_form: str
    direction: str
    completion: str


CASES = (
    Case("before_zero_dont_walk", "dont_walk", "forward", "before_zero"),
    Case("at_zero_dont_walk", "dont_walk", "forward", "at_zero"),
    Case("after_zero_dont_walk", "dont_walk", "forward", "after_zero"),
    Case("before_zero_wait", "wait", "forward", "before_zero"),
    Case("before_zero_hand", "upraised_hand", "forward", "before_zero"),
    Case("before_zero_reverse", "dont_walk", "reverse", "before_zero"),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def point(value, name: str) -> tuple[float, float]:
    require(isinstance(value, (list, tuple)) and len(value) == 2 and
            all(type(x) in (float, int) and isfinite(x) for x in value),
            name + " coordinate missing")
    return float(value[0]), float(value[1])


def near(a, b, tolerance=.5) -> bool:
    x1, y1 = point(a, "first point")
    x2, y2 = point(b, "second point")
    return hypot(x1 - x2, y1 - y2) <= tolerance


def in_polygon(value, polygon) -> bool:
    x, y = point(value, "pedestrian")
    inside = False
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def validate_site(site: Mapping) -> None:
    require(site.get("cell_id") == "C150911" and site.get("actor") == "pedestrian",
            "wrong one-way pedestrian cell")
    require(site.get("layout") == "one_way_road" and
            site.get("highway_public_vehicular_access") is True,
            "reviewed one-way public highway missing")
    for name in ("opendrive", "highway", "crossing", "sidewalk", "signal",
                 "signal_facing", "one_way_direction", "exception_context"):
        require(bool(site.get(name + "_source_sha256")), "original source missing: " + name)
    require(site.get("signal_facing_pedestrian") is True,
            "signal does not face pedestrian crossing")
    polygon = site.get("highway_polygon_xy")
    require(isinstance(polygon, list) and len(polygon) >= 3,
            "highway polygon missing")
    for p in polygon:
        point(p, "highway polygon")
    routes = site.get("crossing_routes", {})
    for direction in ("forward", "reverse"):
        route = routes.get(direction, {})
        waypoints = route.get("waypoints_xy")
        require(route.get("source_sha256") and isinstance(waypoints, list) and
                len(waypoints) >= 3, "sourced crossing route missing: " + direction)
        for p in waypoints:
            point(p, "crossing route")
        require(not in_polygon(waypoints[0], polygon) and
                not in_polygon(waypoints[-1], polygon) and
                any(in_polygon(p, polygon) for p in waypoints[1:-1]),
                "route must traverse the highway between outside endpoints")
        require(site.get("signal_facing_direction") in (direction, "both"),
                "facing signal does not govern crossing direction")
    require(near(routes["forward"]["waypoints_xy"][0],
                 routes["reverse"]["waypoints_xy"][-1]) and
            near(routes["forward"]["waypoints_xy"][-1],
                 routes["reverse"]["waypoints_xy"][0]),
            "opposite crossing routes do not share endpoints")


def construct(adapter, site: Mapping, case: Case, walker_speed_mps: float = 1.2) -> dict:
    validate_site(site)
    require(case in CASES, "unknown countdown crossing case")
    require(0.3 <= walker_speed_mps <= 2.0, "walker speed outside engineering range")
    owned = []
    try:
        route = site["crossing_routes"][case.direction]["waypoints_xy"]
        pedestrian = adapter.spawn_pedestrian(route[0])
        require(pedestrian is not None, "pedestrian spawn failed")
        owned.append(pedestrian)
        adapter.request_pedestrian_signal(signal_form=case.signal_form,
            flashing_from_s=5.0, countdown_zero_s=15.0,
            illuminated=True, facing_direction=case.direction)
        adapter.set_pedestrian_route(pedestrian, route,
            requested_entry_s=6.0,
            requested_completion_s={"before_zero": 14.0,
                "at_zero": 15.0, "after_zero": 16.0}[case.completion],
            walker_speed_mps=walker_speed_mps)
        return {"case_id": case.case_id, "pedestrian": pedestrian,
            "owned": tuple(owned), "route_xy": route,
            "exception_applicability": "unresolved", "legal_judgment": None}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    validate_site(site)
    require(case in CASES and rows, "exact case or original observations missing")
    first_frame = rows[0].get("original_frame")
    require(type(first_frame) is int, "original frame identity missing")
    identity = None
    entry = completion = first_zero = None
    prior_countdown = None
    seen_flashing = False
    route = site["crossing_routes"][case.direction]["waypoints_xy"]
    for i, row in enumerate(rows):
        frame = row.get("original_frame")
        require(frame == first_frame + i and
                type(row.get("time_s")) in (int, float) and
                abs(row["time_s"] - rows[0]["time_s"] - i / 20) <= .005,
                "original frame/time join invalid")
        for name in ("signal_readback_sha256", "pedestrian_pose_sha256",
                     "source_sha256"):
            require(bool(row.get(name)), "original source missing: " + name)
        require(row.get("site_source_sha256") == site["signal_source_sha256"],
                "original signal site changed")
        require(row.get("signal_facing_direction") in (case.direction, "both"),
                "facing signal differs from case")
        ped_id = row.get("pedestrian_id")
        require(bool(ped_id), "original pedestrian identity missing")
        if identity is None:
            identity = ped_id
        require(ped_id == identity, "pedestrian identity changed")
        require(type(row.get("illuminated")) is bool and
                type(row.get("flashing")) is bool and
                type(row.get("countdown_present")) is bool,
                "original signal state readback missing")
        value = row.get("countdown_value")
        if row["countdown_present"]:
            require(type(value) is int and value >= 0,
                    "legible original countdown value missing")
            if prior_countdown is not None:
                require(value <= prior_countdown and value >= prior_countdown - 1,
                        "original countdown sequence invalid")
            prior_countdown = value
        else:
            require(first_zero is not None and not row["flashing"] and value is None,
                    "countdown disappeared before displayed zero")
        if row["flashing"]:
            require(row["illuminated"] and row["countdown_present"] and
                    row.get("signal_form") == case.signal_form,
                    "flashing indication or legible countdown differs from case")
            seen_flashing = True
        elif seen_flashing and value is not None and value > 0:
            raise ValueError("flashing ended before countdown zero")
        if value == 0 and first_zero is None:
            first_zero = frame
        position = row.get("pedestrian_xy")
        if in_polygon(position, site["highway_polygon_xy"]) and entry is None:
            require(row["flashing"] and row["illuminated"] and value is not None and value > 0,
                    "pedestrian entered outside flashing countdown")
            entry = frame
        if (entry is not None and
                not in_polygon(position, site["highway_polygon_xy"]) and
                near(position, route[-1]) and completion is None):
            completion = frame
    require(seen_flashing and entry is not None and completion is not None and
            first_zero is not None and entry < completion,
            "original flashing entry, zero or highway completion missing")
    relation = ("before_zero" if completion < first_zero else
                "at_zero" if completion == first_zero else "after_zero")
    require(relation == case.completion,
            "actual completion differs from selected zero-boundary case")
    return {"case_id": case.case_id, "first_original_frame": first_frame,
            "last_original_frame": first_frame + len(rows) - 1,
            "frame_count": len(rows), "entry_original_frame": entry,
            "completion_original_frame": completion,
            "first_zero_original_frame": first_zero,
            "completion_relation": relation, "signal_form": case.signal_form,
            "crossing_direction": case.direction,
            "exception_applicability": "unresolved", "legal_judgment": None}
