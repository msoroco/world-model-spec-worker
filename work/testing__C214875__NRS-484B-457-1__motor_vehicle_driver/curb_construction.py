"""Source-reviewed placement requests for the right-curb position branch.

Targets are construction requests. Original wheel history supplies measurements.
"""
from __future__ import annotations

import math
from pathlib import Path

from curb_geometry import ASSIGNMENT, INCH_M, load_site, measure_right_wheels

TARGETS = {
    "park_17in_parallel": ("park", 17, 0),
    "park_18in_parallel": ("park", 18, 0),
    "park_19in_parallel": ("park", 19, 0),
    "park_17in_skew": ("park", 17, 8),
    "stop_18in_parallel": ("stop", 18, 0),
}


def build_plan(site_packet, case_id, *, fallback=False):
    """Request a vehicle pose from surveyed curb tangent and real wheel geometry."""
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("unknown right-curb assignment")
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    if variant not in TARGETS or type(fallback) is not bool:
        raise ValueError("unknown exact right-curb case or candidate")
    site = load_site(Path(site_packet), case_id)
    activity, inches, angle_deg = TARGETS[variant]
    curb = site["right_curb_xy_m"]
    start = curb[0]
    end = curb[-1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 4:
        raise ValueError("surveyed curb too short for a vehicle")
    tx, ty = dx / length, dy / length
    side = site.get("roadway_side_of_curb")
    if side not in ("left", "right"):
        raise ValueError("reviewed roadway side of right curb missing")
    sign = 1 if side == "left" else -1
    nx, ny = sign * -ty, sign * tx
    axle = site.get("reviewed_right_wheel_axle_spacing_m")
    if type(axle) not in (int, float) or not 1.5 <= axle <= 5:
        raise ValueError("reviewed vehicle wheelbase missing")
    curb_station = site.get("reviewed_curb_station_m")
    if type(curb_station) not in (int, float) or not axle <= curb_station <= length - axle:
        raise ValueError("reviewed parking station missing")
    if fallback:
        curb_station += .5
        if curb_station > length - axle / 2:
            raise ValueError("fallback station leaves reviewed curb")
    theta = math.radians(angle_deg)
    hx, hy = tx * math.cos(theta) + nx * math.sin(theta), ty * math.cos(theta) + ny * math.sin(theta)
    # For a skewed car, the rear wheel is the nearer wheel. The target is the
    # maximum of the two distances; no angle is interpreted as a legal cutoff.
    front_offset = inches * INCH_M
    rear_offset = front_offset - axle * math.sin(theta)
    if rear_offset <= .05:
        raise ValueError("skew target crosses surveyed curb")
    rear = [start[0] + tx * curb_station + nx * rear_offset,
            start[1] + ty * curb_station + ny * rear_offset]
    front = [rear[0] + hx * axle, rear[1] + hy * axle]
    requested = measure_right_wheels(front, rear, curb)
    if abs(requested["max_right_wheel_distance_inches"] - inches) > .01:
        raise ValueError("surveyed curb is not straight at requested pose")
    return {
        "assignment_id": ASSIGNMENT, "case_id": case_id,
        "candidate_id": "fallback1" if fallback else "primary",
        "reviewed_site_packet": str(Path(site_packet)),
        "reviewed_sources": site["sources"],
        "activity_request": activity,
        "target_right_wheel_distance_inches": inches,
        "target_alignment_deg": angle_deg,
        "requested_right_rear_wheel_xy_m": rear,
        "requested_right_front_wheel_xy_m": front,
        "requested_max_right_wheel_distance_inches": requested["max_right_wheel_distance_inches"],
        "controller": {"approach_route_xy_m": site["parking_route_xy_m"],
                       "hold_brake_for_s": 25, "park_brake": activity == "park"},
        "capture": {"rate_hz": 20, "frame_count": 900,
                    "cameras": ["overview", "approach", "reference_corner", "driver_reference"]},
        "physical_completion": "pending_original_native_readback",
        "legal_judgment": "unresolved",
    }
