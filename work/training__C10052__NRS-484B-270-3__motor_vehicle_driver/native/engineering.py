"""Unselected C10052 candidate parameters and source-measurable triggers."""
from geometry import STOP_X_M, STOP_Y_M

NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def parameters(suffix, candidate):
    if suffix not in STOP_Y_M or candidate not in NAMES:
        raise ValueError('Unknown exact C10052 case or candidate')
    values = {'start_x_m': -45.0, 'stop_x_m': STOP_X_M,
              'stop_y_m': STOP_Y_M[suffix], 'approach_speed_mps': 5.0,
              'braking_start_m': 6.0, 'settle_speed_mps': .1,
              'settle_duration_s': 2.0, 'camera_profile': 'standard'}
    if candidate == 'fallback1':
        values['start_x_m'] = -55.0
    elif candidate == 'fallback2':
        values['braking_start_m'] = 9.0
    elif candidate == 'fallback3':
        values['camera_profile'] = 'wide'
    return values


TRIGGERS = {
    'fallback1': {'source': 'original Native pose and route start survey',
                  'metric': 'usable approach distance before lateral shift',
                  'failure_condition': 'primary has less than 15 m before shift or spawn/route survey fails',
                  'changed_knobs': ['approach start x -45 m to -55 m']},
    'fallback2': {'source': 'original Native pose, velocity and full-body trace',
                  'metric': 'stopped-body target error and stationary duration',
                  'failure_condition': 'target center error exceeds 0.25 m or 2.0 s under 0.1 m/s is absent',
                  'changed_knobs': ['braking onset 6 m to 9 m before stop']},
    'fallback3': {'source': 'four original source videos joined to Native frames',
                  'metric': 'fraction of stopped frames showing full body and facility edge',
                  'failure_condition': 'fraction falls below 0.95 in any required view',
                  'changed_knobs': ['facility/overview camera FOV 90 to 105 degrees and elevated mount']},
}
