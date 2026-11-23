"""Portable intersection geometry and warning control plan for C109035.

The outputs are authored targets. Original capture must measure realized positions
and device states independently.
"""
from __future__ import annotations

import math


CASE_KNOBS = {
    "response_siren_pedestrian": {"event": "emergency_call", "siren": True, "lamps": False},
    "response_lamps_only": {"event": "emergency_call", "siren": False, "lamps": True},
    "response_silent": {"event": "emergency_call", "siren": False, "lamps": False},
    "pursuit_actual_siren": {"event": "immediate_pursuit_actual", "siren": True, "lamps": False},
    "pursuit_suspected_siren": {"event": "immediate_pursuit_suspected", "siren": True, "lamps": False},
    "unqualified_siren": {"event": "none", "siren": True, "lamps": False},
    "unqualified_lamps_only": {"event": "none", "siren": False, "lamps": True},
}


def scene_geometry(approach: str, crossing_station_m: float = 0.0) -> dict:
    """Place the recipient on the sidewalk for either travel direction.

    Road axis runs east/west; the vehicle uses its right-hand lane. The
    pedestrian's lateral position is outside the vehicle lane and ahead of the
    approach. This is an engineering layout, not an actual map feasibility claim.
    """
    if approach not in ("eastbound", "westbound"):
        raise ValueError("Unknown approach")
    direction = 1 if approach == "eastbound" else -1
    lane_y = -1.75 * direction
    start_x = crossing_station_m - 60.0 * direction
    pedestrian_x = crossing_station_m + 5.0 * direction
    pedestrian_y = -4.0 * direction
    distance = math.hypot(pedestrian_x - start_x, pedestrian_y - lane_y)
    if distance <= 20 or abs(pedestrian_y - lane_y) < 2:
        raise ValueError("Pedestrian approach geometry invalid")
    return {
        "approach": approach,
        "ego_spawn_xy_m": [start_x, lane_y],
        "ego_heading_deg": 0 if direction == 1 else 180,
        "ego_target_xy_m": [crossing_station_m + 25 * direction, lane_y],
        "pedestrian_spawn_xy_m": [pedestrian_x, pedestrian_y],
        "pedestrian_role": "approach_warning_recipient",
        "pedestrian_distance_at_spawn_m": round(distance, 3),
        "intersection_station_m": crossing_station_m,
    }


def control_plan(case_suffix: str) -> dict:
    if case_suffix not in CASE_KNOBS:
        raise ValueError("Unknown case")
    knobs = CASE_KNOBS[case_suffix]
    return {
        "case_suffix": case_suffix,
        "event_context": knobs["event"],
        "siren_command_window_s": [8.0, 22.0] if knobs["siren"] else [],
        "warning_lamp_command_window_s": [8.0, 22.0] if knobs["lamps"] else [],
        "pedestrian_motion": "sidewalk_wait_then_cross_after_vehicle_passes",
        "capture_duration_s": 45,
        "capture_rate_hz": 20,
    }
