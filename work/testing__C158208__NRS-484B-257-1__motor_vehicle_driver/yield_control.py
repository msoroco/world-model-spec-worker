"""CARLA-lazy engineering controller for the nearest-view response comparison.

The two diagnostic constructions share approach geometry and target speed. The
response switch changes only the brake decision when through traffic occupies
the conflict interval. An original capture must establish the observed state.
"""

from __future__ import annotations

import math


KINDS = {
    "nearest_view_response", "nearest_view_uninterrupted",
    "marked_stop_line_response", "marked_stop_line_uninterrupted",
    "near_side_marked_crosswalk_response", "near_side_marked_crosswalk_uninterrupted",
    "near_side_sidewalk_derived_crosswalk_response",
    "near_side_sidewalk_derived_crosswalk_uninterrupted",
    "approaching_phase_probe", "later_history_probe", "nearest_view_stopped",
}


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def control(kind: str, observation: dict, *, target_speed_mps: float = 4.0) -> dict:
    if kind not in KINDS:
        raise ValueError("unknown exact construction")
    speed = _finite(observation["ego_speed_mps"], "ego_speed_mps")
    distance = _finite(observation["distance_to_view_point_m"], "distance_to_view_point_m")
    target = _finite(target_speed_mps, "target_speed_mps")
    if speed < 0 or target <= 0 or distance < -20:
        raise ValueError("invalid engineering geometry or speed")
    occupied = observation.get("through_vehicle_in_conflict_interval")
    if not isinstance(occupied, bool):
        raise ValueError("through-vehicle conflict observation required")
    if observation.get("yield_sign_governs_approach") is not True:
        raise ValueError("governing yield sign observation required")
    if observation.get("viewpoint_source_verified") is not True:
        raise ValueError("source-verified viewpoint required")
    near_view = distance <= 8.0
    response = near_view and ((kind.endswith("_response") and occupied) or
                              kind == "nearest_view_stopped")
    if response:
        return {"throttle": 0.0, "brake": min(1.0, 0.35 + speed / 6.0),
                "steer": 0.0, "engineering_state": "yield_hold"}
    error = target - speed
    return {"throttle": min(0.45, max(0.0, error * 0.12)),
            "brake": min(0.4, max(0.0, -error * 0.12)),
            "steer": 0.0, "engineering_state": "approach_or_cross"}
