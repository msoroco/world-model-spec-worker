"""Deterministic 20 Hz stop policy for a future sourced Native route.

The requested stop target must come from a map and device extent, not from this
diagnostic. This controller uses observed distance and speed on every frame.
"""

from __future__ import annotations

import math

FRAMES = 600


def command(frame, remaining_route_m, observed_speed_mps):
    if type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Unknown Native frame")
    for value in (remaining_route_m, observed_speed_mps):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Missing observed Native distance or speed")
    if observed_speed_mps < 0 or remaining_route_m < -1.0:
        raise ValueError("Invalid speed or stop overshoot")
    if remaining_route_m <= 0.4:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0, "phase": "hold"}
    brake_distance = observed_speed_mps * observed_speed_mps / 4.0 + 1.0
    if remaining_route_m <= brake_distance:
        return {"throttle": 0.0, "brake": 0.7, "steer": 0.0, "phase": "brake"}
    return {"throttle": 0.2, "brake": 0.0, "steer": 0.0, "phase": "approach"}


def prove_trace(rows):
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second control trace")
    phases = []
    for i, row in enumerate(rows):
        if row.get("native_frame") != i or abs(row.get("time_s", -1) - i / 20) > 1e-6:
            raise ValueError("Controller frame/time join failed")
        output = command(i, row.get("remaining_route_m"), row.get("observed_speed_mps"))
        phases.append(output["phase"])
        if i >= 100 and (output["phase"] != "hold" or row["observed_speed_mps"] > 0.1):
            raise ValueError("Continuous destination rest not observed")
    return {"frames": FRAMES, "phase_counts": {p: phases.count(p) for p in set(phases)},
            "synthetic_control_proof": True, "physical_execution": False}
