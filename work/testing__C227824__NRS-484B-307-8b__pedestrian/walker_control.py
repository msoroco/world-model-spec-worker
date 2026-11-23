"""Lazy CARLA walker request for the C227824 entry and wait cases.

The caller owns actor creation, the source-hashed scene, signal timing and world
ticks. This controller only issues a movement request; it never claims motion.
"""
from __future__ import annotations

import math


def _xy(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("walker target must be an xy pair")
    result = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("walker target is nonfinite")
    return result


def request(actor, carla, *, entry_request, target_xy_m, speed_mps):
    """Request walk toward a map-reviewed target or hold position outside."""
    if entry_request not in {"entry", "wait"}:
        raise ValueError("unsupported walker request")
    target = _xy(target_xy_m)
    if not isinstance(speed_mps, (int, float)) or not math.isfinite(speed_mps) or speed_mps <= 0 or speed_mps > 3:
        raise ValueError("walker speed must be finite and within engineering bounds")
    position = actor.get_transform().location
    x, y = float(position.x), float(position.y)
    if not all(math.isfinite(v) for v in (x, y)):
        raise ValueError("nonfinite original walker position")
    if entry_request == "wait":
        direction = carla.Vector3D(0, 0, 0)
        requested_speed = 0.0
    else:
        dx, dy = target[0] - x, target[1] - y
        distance = math.hypot(dx, dy)
        if distance <= 0.05:
            direction = carla.Vector3D(0, 0, 0)
            requested_speed = 0.0
        else:
            direction = carla.Vector3D(dx / distance, dy / distance, 0)
            requested_speed = float(speed_mps)
    control = carla.WalkerControl(direction=direction, speed=requested_speed, jump=False)
    actor.apply_control(control)
    return {"requested_speed_mps": requested_speed,
            "target_xy_m": list(target), "entry_request": entry_request,
            "applied": True, "realized_motion_claimed": False}
