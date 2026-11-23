"""Construction speed targets for the five C158208 nearest-view yield cases.

Targets express staged motion, not a legal speed or hazard threshold. The
saved finalizer must measure what happened from the original Native frames.
"""

from dataclasses import dataclass
import math

PREFIX = 'testing__C158208__NRS-484B-257-1__motor_vehicle_driver__'
SUFFIXES = (
    'yield_nearest_slowed',
    'yield_nearest_stopped',
    'yield_nearest_unchanged_speed',
    'yield_nearest_through_occupied',
    'yield_nearest_through_approaching',
)


@dataclass(frozen=True)
class Stage:
    case_id: str
    approach_speed_mps: float = 8.0
    view_speed_mps: float = 2.0
    crossing_speed_mps: float = 4.0
    view_bracket_m: float = 15.0

    def __post_init__(self):
        if self.case_id not in {PREFIX + suffix for suffix in SUFFIXES}:
            raise ValueError('Unknown exact C158208 case')
        values = (self.approach_speed_mps, self.view_speed_mps,
                  self.crossing_speed_mps, self.view_bracket_m)
        if any(not isinstance(x, (int, float)) or isinstance(x, bool)
               or not math.isfinite(x) or x <= 0 for x in values):
            raise ValueError('Invalid construction speed or bracket')
        if self.view_speed_mps >= self.approach_speed_mps:
            raise ValueError('Slowed case needs a lower target speed')

    def target(self, distance_to_intersection_m, *, within_intersection,
               through_vehicle_clear):
        if (not isinstance(distance_to_intersection_m, (int, float))
                or isinstance(distance_to_intersection_m, bool)
                or not math.isfinite(distance_to_intersection_m)
                or distance_to_intersection_m < 0):
            raise ValueError('Missing Native approach distance')
        if type(within_intersection) is not bool or type(through_vehicle_clear) is not bool:
            raise ValueError('Missing Native crossing state')
        if self.case_id.endswith('__yield_nearest_unchanged_speed'):
            return self.approach_speed_mps
        if within_intersection:
            return self.crossing_speed_mps
        if distance_to_intersection_m > self.view_bracket_m:
            return self.approach_speed_mps
        if self.case_id.endswith('__yield_nearest_stopped') and not through_vehicle_clear:
            return 0.0
        if through_vehicle_clear:
            return self.crossing_speed_mps
        return self.view_speed_mps


def speed_control(target_mps, observed_mps, *, gain=.25):
    if any(not isinstance(x, (int, float)) or isinstance(x, bool)
           or not math.isfinite(x) or x < 0 for x in (target_mps, observed_mps)):
        raise ValueError('Missing observed or target speed')
    if not isinstance(gain, (int, float)) or isinstance(gain, bool) or not 0 < gain <= 1:
        raise ValueError('Invalid speed gain')
    delta = (target_mps - observed_mps) * gain
    return {'throttle': min(1.0, max(0.0, delta)),
            'brake': min(1.0, max(0.0, -delta))}
