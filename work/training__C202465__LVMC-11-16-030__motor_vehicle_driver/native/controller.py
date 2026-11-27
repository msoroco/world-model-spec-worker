"""Measured-speed feedback for straight reviewed grade-crossing approach."""

from __future__ import annotations

from math import isfinite

from rail_sight import FRAME_COUNT, FRAME_RATE, speed_request


def control(frame, observed_speed_mps, speed_mode, *, gain=1.0):
    if not isinstance(frame, int) or not 0 <= frame < FRAME_COUNT:
        raise ValueError("original 600-frame control index required")
    speed = float(observed_speed_mps)
    if not isfinite(speed) or speed < 0:
        raise ValueError("original measured speed required")
    if gain not in (1.0, 1.25):
        raise ValueError("declared primary or fallback feedback gain required")
    target = speed_request(speed_mode)
    error = target - speed
    throttle = max(0.0, min(.7, .22 + gain * .18 * error)) if error >= -.1 else 0.0
    brake = max(0.0, min(.65, gain * .22 * -error)) if error < -.1 else 0.0
    return {"throttle": throttle, "brake": brake, "steer": 0.0,
            "requested_speed_mps": target,
            "source": "original_speed_feedback_not_legal_outcome",
            "frame": frame, "physical_target_met": None}
