"""Feedback speed request for the three unposted-road comparison cases."""

from __future__ import annotations

import math

RATE_HZ = 20
FRAMES = 600
MPH_TO_MPS = 0.44704
TARGET_MPH = {"slow": 20.0, "at_default": 25.0, "fast": 30.0}


def command(case, frame, observed_speed_mps):
    if case not in TARGET_MPH or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Unknown speed case or frame")
    if (isinstance(observed_speed_mps, bool) or not isinstance(observed_speed_mps, (int, float))
            or not math.isfinite(observed_speed_mps) or observed_speed_mps < 0):
        raise ValueError("Missing original observed speed")
    error = TARGET_MPH[case] * MPH_TO_MPS - observed_speed_mps
    return {"throttle": min(0.35, max(0.0, error * 0.08)),
            "brake": min(0.5, max(0.0, -error * 0.08)),
            "steer": 0.0, "target_speed_mph": TARGET_MPH[case]}


def validate_observed(case, rows):
    if case not in TARGET_MPH or len(rows) != FRAMES:
        raise ValueError("Unknown case or incomplete 30-second speed trace")
    within = 0
    for index, row in enumerate(rows):
        if row.get("video_frame") != index or abs(row.get("time_s", -1) - index / RATE_HZ) > 1e-6:
            raise ValueError("Frame/time join failed")
        observed = row.get("observed_speed_mps")
        command(case, index, observed)
        if abs(observed / MPH_TO_MPS - TARGET_MPH[case]) <= 1.0:
            within += 1
    if within < FRAMES - 100:
        raise ValueError("Requested speed not observed for enough frames")
    return {"case": case, "frames_within_one_mph_of_request": within,
            "physical_completion_observed": True, "legal_compliance": "unassessed"}
