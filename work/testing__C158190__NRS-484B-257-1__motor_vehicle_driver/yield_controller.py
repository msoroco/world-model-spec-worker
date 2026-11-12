"""Portable speed staging for C158190's selected yield-sign comparison.

Distances and crossing state must be read from the eventual Native runner.
These speeds are construction targets, not legal hazard or yielding cutoffs.
"""
from dataclasses import dataclass
import math

PREFIX = 'testing__C158190__NRS-484B-257-1__motor_vehicle_driver__'


@dataclass(frozen=True)
class Stage:
    case_id: str
    approach_speed_mps: float = 6.0
    view_speed_mps: float = 2.0
    clear_speed_mps: float = 4.0
    view_bracket_m: float = 15.0

    def __post_init__(self):
        allowed = ('yield_nearest_view_through_approaches',
                   'yield_nearest_view_through_entered',
                   'yield_nearest_view_clear',
                   'yield_nearest_view_no_slow')
        if self.case_id not in {PREFIX + suffix for suffix in allowed}:
            raise ValueError('Unknown exact C158190 case')
        if any(not math.isfinite(value) or value <= 0 for value in
               (self.approach_speed_mps, self.view_speed_mps,
                self.clear_speed_mps, self.view_bracket_m)):
            raise ValueError('Invalid staging parameters')
        if self.view_speed_mps >= self.approach_speed_mps:
            raise ValueError('View-stage construction must slow the ego')

    def target(self, distance_to_intersection_m, *, within_intersection,
               through_vehicle_clear):
        if (not isinstance(distance_to_intersection_m, (int, float))
                or not math.isfinite(distance_to_intersection_m)
                or distance_to_intersection_m < 0):
            raise ValueError('Missing Native approach distance')
        if type(within_intersection) is not bool or type(through_vehicle_clear) is not bool:
            raise ValueError('Missing Native crossing state')
        if self.case_id.endswith('__yield_nearest_view_no_slow'):
            return self.approach_speed_mps
        if within_intersection:
            return self.clear_speed_mps
        if distance_to_intersection_m <= self.view_bracket_m:
            return self.clear_speed_mps if through_vehicle_clear else self.view_speed_mps
        return self.approach_speed_mps


def speed_control(target_mps, observed_mps, *, gain=.25):
    """Simple bounded longitudinal command for a CARLA adapter to apply."""
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0
           for x in (target_mps, observed_mps)):
        raise ValueError('Missing observed or target speed')
    delta = (target_mps - observed_mps) * gain
    return {'throttle': min(1.0, max(0.0, delta)),
            'brake': min(1.0, max(0.0, -delta))}
