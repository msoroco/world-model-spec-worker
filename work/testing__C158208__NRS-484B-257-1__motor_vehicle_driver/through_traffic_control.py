"""Engineering speed schedule for the source-reviewed through vehicle."""
from __future__ import annotations

import math


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return float(value)


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("reviewed through-vehicle motion plan required")
    target = finite(plan.get("target_speed_mps"), "through target speed")
    delay = finite(plan.get("start_delay_s"), "through start delay")
    if not 0 < target <= 25 or not 0 <= delay < 45:
        raise ValueError("through speed or delay outside engineering capture range")
    if plan.get("steering_mode") != "follow_reviewed_route_axis":
        raise ValueError("through steering must follow reviewed route axis")
    return {"target_speed_mps": target, "start_delay_s": delay,
            "steering_mode": "follow_reviewed_route_axis"}


def control(plan: dict, elapsed_s: float, speed_mps: float) -> dict:
    settings = validate_plan(plan)
    elapsed = finite(elapsed_s, "through elapsed time")
    speed = finite(speed_mps, "through observed speed")
    if elapsed < 0 or speed < 0:
        raise ValueError("through time or speed cannot be negative")
    if elapsed < settings["start_delay_s"]:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0,
                "engineering_state": "scheduled_hold"}
    error = settings["target_speed_mps"] - speed
    return {"throttle": min(0.55, max(0.0, error * 0.18)),
            "brake": min(0.6, max(0.0, -error * 0.2)),
            "steer": 0.0, "engineering_state": "through_route_motion"}
