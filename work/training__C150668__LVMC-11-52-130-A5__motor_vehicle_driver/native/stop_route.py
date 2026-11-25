"""Feedback stop request for paired sidewalk-fixture side clearances."""

from __future__ import annotations

import math

FRAMES = 600
RATE_HZ = 20
STOP_X_M = {"outside": 10.0, "side_band": 5.0, "front": 1.0,
            "at_five_feet": 5.524}


def command(case, frame, observed_x_m, observed_speed_mps, brake_margin_m=1.5):
    if case not in STOP_X_M or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Unknown stop case or frame")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (observed_x_m, observed_speed_mps)) or observed_speed_mps < 0:
        raise ValueError("Missing observed Native pose or speed")
    remaining = STOP_X_M[case] - observed_x_m
    if remaining < -1.0:
        raise ValueError("Vehicle overshot requested stop")
    if not isinstance(brake_margin_m, (int, float)) or not 0.5 <= brake_margin_m <= 3.0:
        raise ValueError("Invalid brake margin")
    brake_distance = observed_speed_mps ** 2 / 4.0 + brake_margin_m
    if remaining <= 0.5:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0, "phase": "hold"}
    if remaining <= brake_distance:
        return {"throttle": 0.0, "brake": 0.65, "steer": 0.0, "phase": "brake"}
    return {"throttle": 0.2, "brake": 0.0, "steer": 0.0, "phase": "approach"}


def validate_observed(case, rows):
    if case not in STOP_X_M or len(rows) != FRAMES:
        raise ValueError("Unknown case or incomplete 30-second trace")
    for index, row in enumerate(rows):
        if row.get("video_frame") != index or abs(row.get("time_s", -1) - index / RATE_HZ) > 1e-6:
            raise ValueError("Frame/time join failed")
        x = row.get("observed_x_m")
        speed = row.get("observed_speed_mps")
        command(case, index, x, speed)
        if index >= 100 and (abs(x - STOP_X_M[case]) > 0.5 or speed > 0.1):
            raise ValueError("Requested stop not continuously observed")
    return {"case": case, "stop_frames": FRAMES - 100,
            "physical_completion_observed": True, "legal_compliance": "unassessed"}
