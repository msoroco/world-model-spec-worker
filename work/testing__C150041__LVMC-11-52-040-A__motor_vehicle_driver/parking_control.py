"""CARLA-lazy approach and stationary-hold controls for a reviewed scene draft.

Tolerances are engineering controller values, never statutory thresholds.
Original frame/pose/control history must later prove any realized hold.
"""
from __future__ import annotations

import math

from parking_measurement import unit


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return float(value)


def step(scene, observation):
    target = scene["target_pose"]
    center = observation["center_xy_m"]
    if len(center) != 2:
        raise ValueError("observed center needs XY")
    position = tuple(_finite(value, "observed center") for value in center)
    heading = unit(observation["forward_xy"])
    speed = _finite(observation["speed_m_s"], "observed speed")
    if speed < 0:
        raise ValueError("observed speed must be nonnegative")
    goal = target["target_center_xy_m"]
    delta = tuple(float(goal[i]) - position[i] for i in (0, 1))
    distance = math.hypot(*delta)
    desired = unit(target["target_forward_xy"])
    heading_error = math.degrees(math.atan2(heading[0] * desired[1] - heading[1] * desired[0],
                                            heading[0] * desired[0] + heading[1] * desired[1]))
    # These are explicit controller tolerances, not interpretations of the law.
    position_ok = distance <= 0.35
    heading_ok = abs(heading_error) <= 3.0
    stopped = speed <= 0.15
    if position_ok and heading_ok:
        return {"phase": "stationary_hold" if stopped else "braking",
                "throttle": 0.0, "steer": 0.0, "brake": 1.0,
                "engineering_position_error_m": distance,
                "engineering_heading_error_deg": heading_error,
                "realized_hold_claimed": False}
    if distance <= 0.6 or abs(heading_error) >= 45:
        return {"phase": "needs_maneuver_review", "throttle": 0.0,
                "steer": 0.0, "brake": 1.0,
                "engineering_position_error_m": distance,
                "engineering_heading_error_deg": heading_error,
                "realized_hold_claimed": False}
    bearing = math.atan2(delta[1], delta[0])
    current = math.atan2(heading[1], heading[0])
    # Blend the approach bearing into the requested final heading before arrival.
    final_bearing = math.atan2(desired[1], desired[0])
    target_weight = min(0.7, max(0.0, (4.0 - distance) / 4.0))
    relative = math.atan2(math.sin(final_bearing - bearing),
                          math.cos(final_bearing - bearing))
    guided_bearing = bearing + target_weight * relative
    steering_error = math.atan2(math.sin(guided_bearing - current),
                                math.cos(guided_bearing - current))
    steer = min(0.65, max(-0.65, 1.2 * steering_error))
    throttle = 0.25 if distance > 2 and speed < 4 else 0.08
    brake = 0.0 if speed < 4 else 0.4
    return {"phase": "approach", "throttle": throttle if brake == 0 else 0.0,
            "steer": steer, "brake": brake,
            "engineering_position_error_m": distance,
            "engineering_heading_error_deg": heading_error,
            "realized_hold_claimed": False}


def apply(vehicle, command, carla_module):
    """The caller supplies CARLA; this module is importable in a CPU-only host."""
    control = carla_module.VehicleControl(throttle=command["throttle"],
                                          steer=command["steer"], brake=command["brake"])
    vehicle.apply_control(control)
    return control
