"""Build the assigned officer-governed intersection scene through an adapter.

The adapter owns simulator resources. This module checks the reviewed geometry
and requests actors and controls; it never infers legal conduct from a script.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    suffix: str
    other_phase: str
    other_station_m: float
    officer_directive: str


CASES = (
    Case("occupied_stop", "within", 0.0, "stop"),
    Case("occupied_proceed", "within", 0.0, "proceed"),
    Case("approaching_near_stop", "approaching", 8.0, "stop"),
    Case("approaching_near_proceed", "approaching", 8.0, "proceed"),
    Case("approaching_far_stop", "approaching", 35.0, "stop"),
    Case("approaching_far_proceed", "approaching", 35.0, "proceed"),
)


def _number(value):
    return type(value) in (int, float) and isfinite(value)


def _point(value):
    return isinstance(value, list) and len(value) == 2 and all(_number(x) for x in value)


def validate_site(site: Mapping) -> dict:
    if site.get("cell_id") != "C157964" or site.get("actor") != "motor_vehicle_driver":
        raise ValueError("reviewed site has wrong frozen cell or actor")
    if site.get("control") != "police_officer" or site.get("signal_controls") is not False:
        raise ValueError("reviewed officer control context missing")
    if site.get("layout") != "one_way_to_two_way_intersection" or site.get("maneuver") != "straight":
        raise ValueError("reviewed intersection layout or maneuver differs")
    if site.get("officer_controls_traffic") is not True:
        raise ValueError("active officer governance must be source-reviewed")
    for key in ("jurisdiction", "intersection_geometry", "entrance_controls",
                "officer_location", "officer_directive_visibility", "other_obligation",
                "ego_route", "other_route", "camera_sightlines"):
        digest = site.get(key + "_source_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("reviewed source missing: " + key)
    route = site.get("ego_route_xy")
    if not isinstance(route, list) or len(route) < 2 or not all(_point(x) for x in route):
        raise ValueError("connected ego route missing")
    if not _point(site.get("other_spawn_xy")) or not _point(site.get("officer_spawn_xy")):
        raise ValueError("other participant or officer spawn missing")
    if not _number(site.get("intersection_entry_station_m")) or \
            not _number(site.get("upstream_reference_station_m")) or \
            site["upstream_reference_station_m"] >= site["intersection_entry_station_m"]:
        raise ValueError("physical entry and upstream reference missing")
    if site.get("other_vehicle_obligated_to_stop_or_yield") is not False:
        raise ValueError("other participant obligation unreviewed")
    return dict(site)


def construct(adapter, site: Mapping, case: Case):
    """Create original actors and distinct officer gestures; clean up on failure."""
    if case not in CASES:
        raise ValueError("unknown exact officer case")
    scene = validate_site(site)
    owned = []
    try:
        ego = adapter.spawn_vehicle(scene["ego_route_xy"][0], "ego")
        if ego is None:
            raise ValueError("ego spawn failed")
        owned.append(ego)
        other = adapter.spawn_vehicle(scene["other_spawn_xy"], "other")
        if other is None:
            raise ValueError("other vehicle spawn failed")
        owned.append(other)
        officer = adapter.spawn_officer(scene["officer_spawn_xy"])
        if officer is None:
            raise ValueError("officer spawn failed")
        owned.append(officer)
        adapter.set_ego_route(ego, scene["ego_route_xy"])
        adapter.set_other_phase(other, case.other_phase, case.other_station_m)
        adapter.set_officer_directive(officer, case.officer_directive)
        return {"case_suffix": case.suffix, "actors": tuple(owned),
                "officer_directive_requested": case.officer_directive,
                "other_phase_requested": case.other_phase,
                "other_station_requested_m": case.other_station_m,
                "legal_judgment": None}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
