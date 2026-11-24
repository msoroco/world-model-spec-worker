"""Paired rail-crossing target requests; CPU policy only until Native wiring."""

from __future__ import annotations

import math

FRAMES = 600
RATE_HZ = 20
TARGET_CENTER_X_M = {"clear": 17.0, "space_short": 14.0}


def command(case, frame, observed_center_x_m, observed_speed_mps):
    if case not in TARGET_CENTER_X_M or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Unknown rail case or frame")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (observed_center_x_m, observed_speed_mps)) or observed_speed_mps < 0:
        raise ValueError("Missing observed Native pose or speed")
    remaining = TARGET_CENTER_X_M[case] - observed_center_x_m
    if remaining < -1.0:
        raise ValueError("Vehicle overshot crossing target")
    brake_distance = observed_speed_mps ** 2 / 4.0 + 1.0
    if remaining <= 0.5:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0, "phase": "hold"}
    if remaining <= brake_distance:
        return {"throttle": 0.0, "brake": 0.6, "steer": 0.0, "phase": "brake"}
    return {"throttle": 0.25, "brake": 0.0, "steer": 0.0, "phase": "approach"}


def validate_observed(case, rows):
    if case not in TARGET_CENTER_X_M or len(rows) != FRAMES:
        raise ValueError("Unknown case or incomplete 30-second trace")
    for index, row in enumerate(rows):
        if row.get("video_frame") != index or abs(row.get("time_s", -1) - index / RATE_HZ) > 1e-6:
            raise ValueError("Frame/time join failed")
        x, speed = row.get("vehicle_center_x_m"), row.get("observed_speed_mps")
        command(case, index, x, speed)
        if index >= 100 and (abs(x - TARGET_CENTER_X_M[case]) > 0.5 or speed > 0.1):
            raise ValueError("Requested rail stop not observed")
    return {"case": case, "captured_frames": FRAMES,
            "physical_completion_observed": True, "legal_compliance": "unassessed"}
