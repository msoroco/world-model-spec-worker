"""Portable longitudinal command for a sourced intersection stop target.

The controller returns requests, not proof of observed stopping or necessity.
It consumes original actor position and speed each simulator tick.
"""

from dataclasses import dataclass

from intersection_geometry import Box


@dataclass(frozen=True)
class Command:
    throttle: float
    brake: float
    target_front_gap_m: float
    observed_front_gap_m: float


def front_gap(boundary: Box, approach, cx, cy, heading_deg, length_m):
    if length_m <= 0:
        raise ValueError("Vehicle length must be positive")
    expected = {"east": 180, "west": 0, "north": 270, "south": 90}
    if approach not in expected:
        raise ValueError("Unknown approach")
    if abs(((heading_deg - expected[approach] + 180) % 360) - 180) > 15:
        raise ValueError("Vehicle heading is not aligned with approach")
    if approach == "east":
        return cx - length_m / 2 - boundary.east
    if approach == "west":
        return boundary.west - (cx + length_m / 2)
    if approach == "north":
        return cy - length_m / 2 - boundary.north
    return boundary.south - (cy + length_m / 2)


def command(boundary, approach, cx, cy, heading_deg, speed_mps,
            length_m, target_gap_m, deceleration_mps2=3.0):
    if speed_mps < 0 or target_gap_m < 0 or deceleration_mps2 <= 0:
        raise ValueError("Invalid motion or target")
    gap = front_gap(boundary, approach, cx, cy, heading_deg, length_m)
    remaining = gap - target_gap_m
    if speed_mps < 0.15 and abs(remaining) <= 0.35:
        return Command(0.0, 1.0, target_gap_m, gap)
    # 0.2 s reaction margin plus a minimum 0.4 m stopping reserve.
    braking_distance = speed_mps * speed_mps / (2 * deceleration_mps2) + 0.2 * speed_mps + 0.4
    if remaining <= braking_distance:
        return Command(0.0, min(1.0, max(0.25, speed_mps / 6.0)), target_gap_m, gap)
    return Command(0.25, 0.0, target_gap_m, gap)
