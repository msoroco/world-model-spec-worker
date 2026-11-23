"""Request a railroad-crossing stop using live Native position and speed.

This is an engineering controller. The saved trace must establish whether the
vehicle actually stopped and where; a requested brake is not a legal finding.
"""

from __future__ import annotations

import math


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("invalid Native motion sample: " + name)
    return float(value)


def command(actor, packet: dict, vehicle_control_factory):
    direction = packet["approach_direction"]
    if direction not in (-1, 1):
        raise ValueError("invalid crossing approach direction")
    x = _finite(actor.get_transform().location.x, "actor x")
    velocity = actor.get_velocity()
    speed = math.sqrt(sum(_finite(getattr(velocity, axis), "actor velocity") ** 2
                          for axis in ("x", "y", "z")))
    stop_x = _finite(packet["stop_line_x_m"], "stop line")
    # 1.5 m is a controller footprint margin, not a statutory stopping rule.
    remaining = direction * (stop_x - x) - 1.5
    target = min(5.0, math.sqrt(max(0.0, 4.0 * remaining)))
    error = target - speed
    if remaining <= 0 or target < .2:
        throttle, brake = 0.0, 1.0
    elif error > .3:
        throttle, brake = min(.45, .12 * error), 0.0
    else:
        throttle, brake = 0.0, min(1.0, max(0.0, -.22 * error))
    control = vehicle_control_factory(throttle=throttle, brake=brake, steer=0.0)
    actor.apply_control(control)
    return {"remaining_to_authored_stop_m": remaining,
            "target_speed_mps": target, "measured_speed_mps": speed,
            "throttle": throttle, "brake": brake,
            "observed_stop_confirmed": False}


def step(scene, vehicle_control_factory) -> dict:
    """Actuate every stopped traffic queue at the same Native tick."""
    result = {"ego": command(scene.ego, scene.packet, vehicle_control_factory)}
    if scene.companion is not None:
        result["companion"] = command(scene.companion, scene.packet,
                                      vehicle_control_factory)
    return result
