"""Deterministic approach and stop controller for the restricted-zone draft.

The controller addresses motion only. A posted restriction, driver purpose,
passenger loading and the legal meaning of temporary require separate evidence.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ParkingPlan:
    zone_x0_m: float = 0.0
    zone_x1_m: float = 10.0
    vehicle_half_length_m: float = 2.0
    target_center_x_m: float = 5.0
    max_speed_mps: float = 4.0
    max_deceleration_mps2: float = 3.5

    def validate(self):
        values = tuple(self.__dict__.values())
        if any(not math.isfinite(value) for value in values):
            raise ValueError('Parking plan contains nonfinite geometry or motion')
        if (self.zone_x0_m >= self.zone_x1_m or self.vehicle_half_length_m <= 0
            or not self.zone_x0_m + self.vehicle_half_length_m <
            self.target_center_x_m < self.zone_x1_m - self.vehicle_half_length_m
            or self.max_speed_mps <= 0 or self.max_deceleration_mps2 <= 0):
            raise ValueError('Parking target does not fit restricted zone')


def command(plan: ParkingPlan, center_x_m: float, speed_mps: float) -> dict:
    """Return a bounded Native control request from measured longitudinal state."""
    plan.validate()
    if any(not math.isfinite(value) for value in (center_x_m, speed_mps)) or speed_mps < 0:
        raise ValueError('Invalid measured parking pose or speed')
    remaining = plan.target_center_x_m - center_x_m
    if remaining <= 0.08 and speed_mps <= 0.08:
        return {'phase': 'hold', 'throttle': 0.0, 'brake': 1.0,
                'target_speed_mps': 0.0}
    target_speed = min(plan.max_speed_mps,
                       math.sqrt(2 * plan.max_deceleration_mps2 * max(remaining - 0.08, 0)))
    if speed_mps > target_speed + 0.08:
        return {'phase': 'brake', 'throttle': 0.0,
                'brake': min(1.0, (speed_mps - target_speed) / 1.2),
                'target_speed_mps': target_speed}
    if speed_mps < target_speed - 0.08:
        return {'phase': 'approach', 'throttle': min(1.0, (target_speed - speed_mps) / 1.2),
                'brake': 0.0, 'target_speed_mps': target_speed}
    return {'phase': 'coast', 'throttle': 0.0, 'brake': 0.0,
            'target_speed_mps': target_speed}
