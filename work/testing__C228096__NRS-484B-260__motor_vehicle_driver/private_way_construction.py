"""Source-reviewed Native targets for the nine exact private-way cases.

The targets are engineering requests. Original actor readback and the later
independent source audit determine what occurred; requested yielding is not a
legal verdict or a claim that CARLA completed the maneuver.
"""
from __future__ import annotations

import math


ASSIGNMENT = "testing__C228096__NRS-484B-260__motor_vehicle_driver"
CASES = {
    "enter_right_wait": ("enter", ("right",), "yield_all"),
    "enter_right_intrude": ("enter", ("right",), "continue"),
    "enter_left_wait": ("enter", ("left",), "yield_all"),
    "enter_left_intrude": ("enter", ("left",), "continue"),
    "cross_both_wait": ("cross", ("left", "right"), "yield_all"),
    "cross_both_intrude": ("cross", ("left", "right"), "continue"),
    "enter_both_wait": ("enter", ("left", "right"), "yield_all"),
    "enter_both_yield_one": ("enter", ("left", "right"), "yield_one_only"),
    "enter_no_approach": ("enter", (), "continue"),
}


def _finite_point(value, name):
    if not isinstance(value, list) or len(value) != 2 or any(
        type(number) not in (int, float) or not math.isfinite(number)
        for number in value
    ):
        raise ValueError("reviewed " + name + " point missing")
    return [float(number) for number in value]


def _source(value, name):
    if not isinstance(value, dict) or not isinstance(value.get("path"), str) or \
            not isinstance(value.get("sha256"), str) or len(value["sha256"]) != 64:
        raise ValueError("reviewed source reference missing: " + name)


def build_plan(site: dict, case_id: str, *, spawn_offset_m: float = 0.0) -> dict:
    """Construct routes and actor control requests from a reviewed site packet."""
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong private-way assignment")
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    if variant not in CASES:
        raise ValueError("unknown private-way exact case")
    if type(spawn_offset_m) not in (int, float) or not math.isfinite(spawn_offset_m) or \
            abs(spawn_offset_m) > 5:
        raise ValueError("spawn offset exceeds reviewed engineering adjustment")
    maneuver, sides, policy = CASES[variant]
    if site.get("format") != "worker-private-way-site-v1" or \
            site.get("case_id") != case_id:
        raise ValueError("exact reviewed site packet missing")
    assertions = site.get("reviewed_assertions", {})
    for key in ("private_ownership", "restricted_public_access",
                "destination_public_highway", "permitted_vehicular_use",
                "feasible_connection"):
        if assertions.get(key) is not True:
            raise ValueError("reviewed site condition missing: " + key)
    sources = site.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("source-hashed site records missing")
    for key in ("private_way_ownership", "private_way_access", "highway_status",
                "boundary_map", "connection_map", "native_opendrive_map"):
        _source(sources.get(key), key)
    routes = site.get("routes", {})
    approaches = site.get("approaches", {})
    if set(routes) != {"enter", "cross"} or set(approaches) != {"left", "right"}:
        raise ValueError("both maneuver and highway directions must be reviewed")
    ego_route = [_finite_point(point, maneuver + " route") for point in routes[maneuver]]
    if len(ego_route) < 3:
        raise ValueError("private-way route too short")
    approach_routes = {}
    for side in sides:
        route = [_finite_point(point, side + " approach") for point in approaches[side]]
        if len(route) < 2:
            raise ValueError("highway approach route too short")
        adjusted = route[0].copy()
        direction = [(route[1][i] - route[0][i]) for i in range(2)]
        span = math.hypot(*direction)
        if span < 0.1:
            raise ValueError("degenerate highway approach route")
        adjusted = [adjusted[i] - direction[i] * spawn_offset_m / span for i in range(2)]
        approach_routes[side] = [adjusted] + route[1:]
    return {
        "assignment_id": ASSIGNMENT,
        "case_id": case_id,
        "variant": variant,
        "maneuver": maneuver,
        "reviewed_sources": sources,
        "reviewed_assertions": assertions,
        "ego_route_xy_m": ego_route,
        "highway_approach_routes_xy_m": approach_routes,
        "connection_xy_m": _finite_point(site.get("connection_xy"), "connection"),
        "requested_control_policy": policy,
        "requested_spawn_offset_m": float(spawn_offset_m),
        "approach_speed_requests_mps": {side: 2.0 if side == "left" else 1.2
                                        for side in sides},
        "control_requests": {
            "approach_window_s": [8, 30],
            "ego_hold_window_s": [12, 25] if policy != "continue" else [],
            "yield_one_side": "left" if policy == "yield_one_only" else None,
            "readback_required": ["ego_body", "highway_vehicle_bodies",
                                  "brake", "velocity", "frame_map", "camera_png"],
        },
        "capture": {"rate_hz": 20, "frames": 900, "duration_s": 45,
                    "cameras": ["overview", "approach", "reference_corner",
                                "driver_reference"]},
        "physical_outcome": "pending_original_native_readback",
        "legal_yield_judgment": "unresolved",
    }
