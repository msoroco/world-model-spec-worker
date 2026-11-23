"""Lazy Native construction policy for C158196 yield/active-control probes.

The caller supplies CARLA actors and site observations after checking the map.
This module never creates a sign, crosswalk, or through highway by declaration.
"""

from __future__ import annotations

import math


CASES = {
    "nearest_view_hold": "hold_for_observed_traffic",
    "nearest_view_continue": "continue_through_observed_traffic",
    "nearest_view_clear": "continue_after_clear_observation",
    "active_signal_exception": "observe_signal_governance",
}


def validate_site(site: dict, case: str) -> dict:
    if case not in CASES:
        raise ValueError("unknown exact case")
    if site.get("native_cell_id") != "C158196":
        raise ValueError("wrong Native cell")
    if site.get("layout") != "one_way_to_two_way_intersection":
        raise ValueError("wrong intersection layout")
    if site.get("route_connected") is not True or site.get("through_highway_confirmed") is not True:
        raise ValueError("route and through-highway survey required")
    if site.get("marked_stop_line") is not False:
        raise ValueError("marked stop line exclusion unconfirmed")
    if site.get("near_side_crosswalk") is not False or site.get("sidewalk_derived_crosswalk") is not False:
        raise ValueError("near-side crosswalk exclusion unconfirmed")
    if site.get("officer_controlling") is not False:
        raise ValueError("officer control exclusion unconfirmed")
    if case != "active_signal_exception":
        if site.get("proper_yield_sign") is not True or site.get("yield_sign_governs") is not True:
            raise ValueError("proper governing yield sign not observed")
        if site.get("signal_controlling") is not False:
            raise ValueError("signal exception must be absent in yield case")
    elif site.get("signal_controlling") is not True:
        raise ValueError("active signal exception must be observed")
    view = site.get("nearest_view_station_m")
    entry = site.get("intersection_entry_station_m")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (view, entry)):
        raise ValueError("Native viewpoint and entry geometry missing")
    if view >= entry:
        raise ValueError("viewpoint must precede intersection entry")
    for source in ("map_hash", "device_hash", "raycast_hash", "camera_plan_hash"):
        value = site.get(source)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"{source} source missing")
    return {"case": case, "engineering_policy": CASES[case], "view_station_m": float(view),
            "entry_station_m": float(entry), "source_hashes": {k: site[k] for k in
            ("map_hash", "device_hash", "raycast_hash", "camera_plan_hash")}}


def controller(case: str, site: dict, observed: dict) -> dict:
    """Use observed conflict state for a diagnostic brake policy, not a verdict."""
    construction = validate_site(site, case)
    speed = observed.get("ego_speed_mps")
    front = observed.get("ego_front_station_m")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (speed, front)):
        raise ValueError("original ego speed and body station required")
    if speed < 0:
        raise ValueError("negative speed")
    occupied = observed.get("through_occupied")
    if not isinstance(occupied, bool):
        raise ValueError("observed through-traffic occupancy required")
    near_view = front >= construction["view_station_m"] - 2.0
    if case == "nearest_view_hold" and near_view and occupied:
        return {"throttle": 0.0, "brake": min(1.0, 0.3 + speed / 8.0),
                "steer": 0.0, "state": "engineering_yield_hold"}
    if case == "nearest_view_clear" and occupied:
        raise ValueError("clear-traffic case has occupied through interval")
    if case == "nearest_view_continue" and not occupied:
        raise ValueError("occupied-traffic comparison missing")
    return {"throttle": max(0.0, min(0.45, (4.0 - speed) * 0.12)),
            "brake": max(0.0, min(0.4, (speed - 4.0) * 0.12)),
            "steer": 0.0, "state": "engineering_approach"}
