"""CPU-checkable route request for a connected barrier/trail scene."""

from __future__ import annotations

import math

RATE_HZ = 20
FRAMES = 600
CASE_LATERAL_M = {"outside": 6.0, "within": 0.0}
START_X_M = -50.0
SPEED_MPS = 4.0
BARRIER_X_M = 8.0


def target(case, frame):
    if case not in CASE_LATERAL_M or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Unknown case or frame")
    return {"x_m": START_X_M + SPEED_MPS * frame / RATE_HZ,
            "y_m": CASE_LATERAL_M[case], "target_speed_mps": SPEED_MPS,
            "steering_policy": "track_requested_route"}


def check_scene(scene):
    if scene.get("barrier_x_m") != BARRIER_X_M:
        raise ValueError("Barrier location changed")
    gap = scene.get("barrier_clear_gap_m")
    width = scene.get("vehicle_width_m")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (gap, width)) or gap < width or width <= 0:
        raise ValueError("Barrier lacks vehicle clearance")
    if scene.get("trail_lateral_bounds_m") != [-2.0, 2.0]:
        raise ValueError("Trail boundary changed")
    return {"connected_inside_route_requested": True,
            "physical_clearance_observed": False,
            "outside_lateral_m": CASE_LATERAL_M["outside"],
            "within_lateral_m": CASE_LATERAL_M["within"]}
