"""Feedback parking controller request for the two public-park frontage probes.

The pure policy can be tested on CPU; CARLA actuator wiring remains in the
future Native runner. Positions are engineering coordinates, not legal facts.
"""

from __future__ import annotations

import math

STATIONS_M = {"away": -30.0, "beside": 40.0}
RATE_HZ = 20
TOTAL_FRAMES = 600


def command(case, frame, observed_x_m, observed_speed_mps):
    if case not in STATIONS_M:
        raise ValueError("Unknown parking target")
    if type(frame) is not int or not 0 <= frame < TOTAL_FRAMES:
        raise ValueError("Frame outside 30-second capture")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (observed_x_m, observed_speed_mps)):
        raise ValueError("Missing observed Native pose or speed")
    if observed_speed_mps < 0:
        raise ValueError("Negative observed speed")
    remaining = STATIONS_M[case] - observed_x_m
    if remaining < -1.0:
        raise ValueError("Vehicle overshot parking station")
    # The two cases use exactly the same policy; only station changes.
    braking_distance = observed_speed_mps ** 2 / (2 * 2.0) + 1.5
    if remaining <= 0.5:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0, "phase": "hold"}
    if remaining <= braking_distance:
        return {"throttle": 0.0, "brake": 0.65, "steer": 0.0, "phase": "brake"}
    return {"throttle": 0.22, "brake": 0.0, "steer": 0.0, "phase": "approach"}


def validate_observed_completion(case, rows):
    if case not in STATIONS_M or len(rows) != TOTAL_FRAMES:
        raise ValueError("Unknown case or incomplete 30-second capture")
    settled = 0
    for index, row in enumerate(rows):
        if row.get("video_frame") != index or abs(row.get("time_s", -1) - index / RATE_HZ) > 1e-6:
            raise ValueError("Frame/time join failed")
        x = row.get("observed_x_m")
        speed = row.get("observed_speed_mps")
        command(case, index, x, speed)
        if abs(x - STATIONS_M[case]) <= 0.5 and speed <= 0.1:
            settled += 1
        elif index >= 100:
            raise ValueError("Parking target not continuously held")
    if settled < TOTAL_FRAMES - 100:
        raise ValueError("Parking interval too short")
    return {"case": case, "captured_frames": TOTAL_FRAMES, "settled_frames": settled,
            "physical_completion_observed": True, "legal_compliance": "unassessed"}
