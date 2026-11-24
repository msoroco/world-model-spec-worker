"""Paired motorcycle route requests for source-checked lane position."""

from __future__ import annotations

FRAMES = 600
RATE_HZ = 20
LATERAL_M = {"beside": 1.5, "between": 3.0}


def target(case, frame):
    if case not in LATERAL_M or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Unknown motorcycle case or frame")
    return {"x_m": -30.0 + 2.0 * frame / RATE_HZ,
            "y_m": LATERAL_M[case], "target_speed_mps": 2.0,
            "policy": "track_requested_route"}


def compare_requested_routes():
    beside = [target("beside", index) for index in range(FRAMES)]
    between = [target("between", index) for index in range(FRAMES)]
    if not all(a["x_m"] == b["x_m"] and a["target_speed_mps"] == b["target_speed_mps"]
               for a, b in zip(beside, between)):
        raise ValueError("Longitudinal route or speed changed")
    if not all(a["y_m"] == 1.5 and b["y_m"] == 3.0 for a, b in zip(beside, between)):
        raise ValueError("Lateral comparison variable changed")
    return {"frame_count": FRAMES, "rate_hz": RATE_HZ,
            "only_requested_difference": "lateral_position_m",
            "physical_result": "unobserved"}
