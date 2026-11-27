"""Common longitudinal policy for ground-control and bridge-halt requests."""

TARGET_X_M = {'false': -25.0, 'true': 50.0}
START_X_M = -75.0


def command(case_suffix, frame, x_m, speed_mps):
    if case_suffix not in TARGET_X_M:
        raise ValueError('unknown exact bridge comparison case')
    if frame < 0 or not -100 <= x_m <= 200 or speed_mps < 0:
        raise ValueError('invalid observed control input')
    target = TARGET_X_M[case_suffix]
    remaining = target - x_m
    if remaining > max(5.0, speed_mps * 1.7):
        return {'phase': 'approach', 'throttle': .48 if speed_mps < 12 else .12,
                'brake': 0.0, 'steer': 0.0, 'target_x_m': target}
    if remaining > .5 or speed_mps > .15:
        return {'phase': 'braking', 'throttle': 0.0, 'brake': .9,
                'steer': 0.0, 'target_x_m': target}
    return {'phase': 'hold', 'throttle': 0.0, 'brake': 1.0,
            'steer': 0.0, 'target_x_m': target}


def check():
    if TARGET_X_M != {'false': -25.0, 'true': 50.0}:
        raise ValueError('exact comparison target changed')
    if command('true', 0, START_X_M, 0)['phase'] != 'approach':
        raise ValueError('bridge approach missing')
    if command('false', 200, -25.0, 0)['phase'] != 'hold':
        raise ValueError('ground control hold missing')
    return {'targets_x_m': TARGET_X_M, 'start_x_m': START_X_M,
            'requested_halt_cause': 'voluntary_destination',
            'physical_completion_verified': False}
