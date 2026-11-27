"""Paired 1,000-foot visibility-trigger requests with no physical claim."""
from math import sqrt

import beam_scene as base


FEET = 1000
MODES = {'visibility_dim': 'dim_within_500',
         'visibility_high': 'retain_high'}
CAMERAS = base.CAMERAS
beam_request = base.beam_request


def request(case):
    if case not in MODES:
        raise ValueError('Unknown visibility comparison case')
    plan = base.request('condition_a' if case == 'visibility_dim' else 'condition_b')
    plan['case'] = case
    plan['beam_mode'] = MODES[case]
    plan['lighting']['weather_request'] = 'ControlledFogNight'
    plan['lighting']['fog_density_request'] = 80
    plan['lighting']['trigger_evidence'] = 'Original 1000-foot target and decoded discernibility review required'
    plan['visibility_target'] = {'kind': 'vehicle', 'role': 'oncoming',
                                 'authored_initial_distance_ft': FEET,
                                 'discernibility_claimed': False}
    ego = plan['ego']['start_xyz_m']
    other = plan['oncoming']['start_xyz_m']
    distance_m = FEET * .3048
    other[0] = ego[0] + sqrt(distance_m**2 - (other[1] - ego[1])**2)
    return plan


def validate_request(plan):
    base.validate_request(plan)
    case = plan['case']
    if case not in MODES or plan['beam_mode'] != MODES[case]:
        raise ValueError('Visibility pair identity differs')
    target = plan.get('visibility_target', {})
    if target != {'kind': 'vehicle', 'role': 'oncoming',
                  'authored_initial_distance_ft': FEET,
                  'discernibility_claimed': False}:
        raise ValueError('Visibility target contract differs')
    if plan['lighting'].get('fog_density_request') != 80:
        raise ValueError('Controlled atmosphere request differs')
    ego, other = plan['ego']['start_xyz_m'], plan['oncoming']['start_xyz_m']
    distance_ft = sum((a-b)**2 for a, b in zip(ego, other))**.5/.3048
    if abs(distance_ft - FEET) > 1e-9:
        raise ValueError('Authored 1000-foot target distance differs')
    return {'case': case, 'target_ft': FEET, 'camera_count': 4,
            'frames': 600, 'physical_verified': False}
