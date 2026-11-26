"""Engineering stop/yield control for a flashing-red Native approach proposal.

This module has no CARLA dependency. Original velocity, body and light state must
be read back by the Native runner; a command or this CPU test is not observation.
"""
from dataclasses import dataclass
import math


@dataclass
class State:
    stop_frames: int = 0
    departed: bool = False
    previous_front_x_m: float | None = None


def command(case_suffix: str, front_x_m: float, speed_mps: float,
            reference_x_m: float, conflict_occupied: bool, state: State) -> dict:
    stop_cases = {"probe_a", "crosswalk_stop", "intersection_stop"}
    nonstop_cases = {"probe_b", "crosswalk_no_stop", "intersection_no_stop"}
    if case_suffix not in stop_cases | nonstop_cases:
        raise ValueError("Unknown comparison case")
    if any(type(value) not in (float, int) or not math.isfinite(value) for value in
           (front_x_m, speed_mps, reference_x_m)) or speed_mps < 0:
        raise ValueError("Native body or reference sample invalid")
    if type(conflict_occupied) is not bool:
        raise ValueError("Original conflict readback missing")
    if state.previous_front_x_m is not None and front_x_m < state.previous_front_x_m - .1:
        raise ValueError("Native body moved backwards")
    state.previous_front_x_m = front_x_m
    if case_suffix in stop_cases and not state.departed:
        # 2.5 m/s^2 is an engineering deceleration target, not a legal threshold.
        braking_distance = speed_mps * speed_mps / 5 + 1.5
        if front_x_m >= reference_x_m - braking_distance:
            if speed_mps <= .05 and front_x_m < reference_x_m:
                state.stop_frames += 1
            if state.stop_frames < 30 or conflict_occupied:
                return {"throttle": 0.0, "brake": 1.0, "hand_brake": speed_mps <= .05,
                        "engineering_phase": "pre_reference_stop"}
            state.departed = True
    # Keep post-stop conflict gating common to both probes, isolating the halt.
    if conflict_occupied and front_x_m >= reference_x_m - 2:
        return {"throttle": 0.0, "brake": 1.0, "hand_brake": speed_mps <= .05,
                "engineering_phase": "conflict_yield"}
    return {"throttle": .35 if speed_mps < 5 else 0.0, "brake": 0.0,
            "hand_brake": False, "engineering_phase": "proceed"}
