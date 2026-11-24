"""Paired 30-second bus-entry requests for wheel-to-curb comparison."""

from __future__ import annotations

import math

FRAMES = 600
RATE_HZ = 20
WHEEL_GAP_M = {"near": 0.30, "far": 0.70}


def target(case, frame):
    if case not in WHEEL_GAP_M or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Unknown bus case or frame")
    entering = frame < 100
    return {"target_x_m": -20.0 + 40.0 * min(frame, 100) / 100,
            "target_right_front_wheel_gap_m": WHEEL_GAP_M[case],
            "target_heading_deg": 0.0,
            "target_speed_mps": 4.0 if entering else 0.0,
            "loading_requested": not entering,
            "other_vehicle_target_speed_mps": 4.0}


def check_observed(case, rows):
    if case not in WHEEL_GAP_M or len(rows) != FRAMES:
        raise ValueError("Unknown case or incomplete 30-second observation")
    held = 0
    for frame, row in enumerate(rows):
        if row.get("video_frame") != frame or abs(row.get("time_s", -1) - frame / RATE_HZ) > 1e-6:
            raise ValueError("Frame/time join failed")
        wheel = row.get("observed_right_front_wheel_gap_m")
        speed = row.get("observed_bus_speed_mps")
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
               for x in (wheel, speed)) or wheel < 0 or speed < 0:
            raise ValueError("Missing observed bus wheel or speed")
        if frame >= 100:
            if abs(wheel - WHEEL_GAP_M[case]) > 0.05 or speed > 0.10 or row.get("loading_observed") is not True:
                raise ValueError("Requested loading position not observed")
            held += 1
    return {"case": case, "held_loading_frames": held,
            "physical_completion_observed": True, "legal_compliance": "unassessed"}
