"""Lazy, station-bound engineering speed profiles for the exact crest cases.

Targets distinguish physical constructions. Actual original Native speed history
must be measured independently by crest_speed.py before any case comparison.
"""
from __future__ import annotations

import math


PROFILES = {
    'early_decrease': ((30.0, 12.0), (20.0, 10.0), (10.0, 8.0), (0.0, 8.0)),
    'late_decrease': ((30.0, 12.0), (20.0, 12.0), (10.0, 10.0), (0.0, 8.0)),
    'steady_approach': ((30.0, 12.0), (20.0, 12.0), (10.0, 12.0), (0.0, 12.0)),
}


def target_speed(profile, *, crest_s_m, ego_s_m):
    if profile not in PROFILES:
        raise ValueError('unknown exact speed profile')
    if not all(type(x) in (float, int) and math.isfinite(x) for x in (crest_s_m, ego_s_m)):
        raise ValueError('finite original crest and ego stations required')
    distance = crest_s_m - ego_s_m
    if distance < 0:
        return PROFILES[profile][-1][1]
    for threshold, target in PROFILES[profile]:
        if distance >= threshold:
            return target
    return PROFILES[profile][-1][1]


def step(vehicle, command_factory, profile, *, crest_s_m, ego_s_m, measured_speed_mps,
         steer=0.0, route_end_s_m=None):
    """Apply one CARLA-compatible control without importing CARLA at module load."""
    if type(measured_speed_mps) not in (float, int) or not math.isfinite(measured_speed_mps) or measured_speed_mps < 0:
        raise ValueError('original measured speed required')
    target = target_speed(profile, crest_s_m=crest_s_m, ego_s_m=ego_s_m)
    if route_end_s_m is not None:
        if (type(route_end_s_m) not in (float, int) or
                not math.isfinite(route_end_s_m) or route_end_s_m <= crest_s_m):
            raise ValueError('source-bound route end must follow crest')
        if ego_s_m >= route_end_s_m - 20.0:
            target = 0.0
    error = target - measured_speed_mps
    throttle = min(0.55, max(0.0, 0.18 * error))
    brake = min(0.65, max(0.0, -0.22 * error))
    command = command_factory(throttle=throttle, brake=brake, steer=steer)
    vehicle.apply_control(command)
    return {'target_speed_mps': target, 'measured_speed_mps': measured_speed_mps,
            'throttle': throttle, 'brake': brake,
            'limitation': 'Command output and route-end stop are engineering requests, not evidence of actual slowing or legal necessity.'}
