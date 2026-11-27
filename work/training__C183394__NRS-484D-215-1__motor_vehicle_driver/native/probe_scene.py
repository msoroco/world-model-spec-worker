"""Exact starting geometry for the three physical 500-foot probes.

The target is an authored starting separation. Original Native actor readback
decides the realized distance; this module never asserts exact physical onset.
"""
from math import sqrt

import beam_scene as base

MODES = {name: 'dim_within_500' for name in
         ('distance_below_500ft', 'distance_at_500ft', 'distance_above_500ft')}
CAMERAS = base.CAMERAS
FEET = {'distance_below_500ft': 499,
        'distance_at_500ft': 500,
        'distance_above_500ft': 501}


def request(case):
    if case not in MODES:
        raise ValueError('Unknown physical distance probe')
    plan = base.request('condition_a')
    plan['case'] = case
    plan['distance_probe_target_ft'] = FEET[case]
    ego = plan['ego']['start_xyz_m']
    other = plan['oncoming']['start_xyz_m']
    target_m = FEET[case] * .3048
    lateral_m = other[1] - ego[1]
    other[0] = ego[0] + sqrt(target_m * target_m - lateral_m * lateral_m)
    return plan


def validate_request(plan):
    base.validate_request(plan)
    case = plan['case']
    if case not in FEET or plan.get('distance_probe_target_ft') != FEET[case]:
        raise ValueError('Physical distance probe identity differs')
    ego, other = plan['ego']['start_xyz_m'], plan['oncoming']['start_xyz_m']
    distance_ft = (((ego[0]-other[0])**2 + (ego[1]-other[1])**2)**.5)/.3048
    if abs(distance_ft-FEET[case]) > 1e-9:
        raise ValueError('Authored starting distance differs')
    return {'case': case, 'target_ft': FEET[case], 'physical_verified': False,
            'frames': 600, 'camera_count': 4}
