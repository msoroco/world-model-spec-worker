"""Source-defined two-direction center-point sight rays, without legal verdict."""
from __future__ import annotations

import math
from geometry import (FT_M, OBSERVER_DISTANCES_FT, RADIUS_M, TURN_STATION_M,
                      center_xy, check, obstruction_radius_for_limit,
                      reference_limit_ft, road_height)


def sight_ray(distance_ft: float, direction: int, obstruction_radius_m: float) -> dict:
    if direction not in (-1, 1) or not math.isfinite(distance_ft) or distance_ft <= 0:
        raise ValueError("Invalid approach sight ray")
    reference_limit_ft(obstruction_radius_m)
    distance_m = distance_ft * FT_M
    station = TURN_STATION_M + direction * distance_m
    target = center_xy(TURN_STATION_M)
    observer = center_xy(station)
    # This is a center-reference geometric ray. Real vehicle body visibility,
    # driver eyes, opacity, terrain mesh and pixels remain to be measured.
    closest_radius = RADIUS_M * math.cos(distance_m / (2 * RADIUS_M))
    clearance = closest_radius - obstruction_radius_m
    blocked = clearance < -1e-8
    return {"direction": "increasing_station" if direction > 0 else "decreasing_station",
            "observer_station_m": station, "observer_distance_ft": distance_ft,
            "target_center_xy_m": list(target), "observer_center_xy_m": list(observer),
            "target_road_height_m": road_height(TURN_STATION_M),
            "observer_road_height_m": road_height(station),
            "minimum_ray_radius_m": closest_radius,
            "obstruction_radius_m": obstruction_radius_m,
            "signed_radial_clearance_m": clearance,
            "reference_ray_blocked": blocked,
            "actual_vehicle_visibility_proven": False}


def measure_case(suffix: str) -> dict:
    if suffix not in OBSERVER_DISTANCES_FT:
        raise ValueError("Unknown C104538 case")
    check()
    requested = OBSERVER_DISTANCES_FT[suffix]
    radius = obstruction_radius_for_limit(requested)
    rays = [sight_ray(500, direction, radius) for direction in (-1, 1)]
    tangent = [sight_ray(requested, direction, radius) for direction in (-1, 1)]
    return {"format": "c104538-authored-sightline-v1", "case_suffix": suffix,
            "requested_reference_limit_ft": requested,
            "measured_authored_reference_limit_ft": reference_limit_ft(radius),
            "inner_obstruction_radius_m": radius,
            "statutory_probe_distance_ft": 500, "rays_at_500_ft": rays,
            "tangent_rays_at_limit": tangent,
            "both_directions_sampled": True, "native_verified": False,
            "actual_vehicle_visibility_proven": False,
            "legal_verdict_claimed": False,
            "scope": "authored center-reference geometry; no Native body, driver-eye or pixel proof"}
