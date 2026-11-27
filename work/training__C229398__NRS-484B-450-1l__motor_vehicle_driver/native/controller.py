"""One feedback policy for the curb-clear and highway-side stopping probes."""
import math

RATE_HZ = 20
TOTAL_FRAMES = 600
TARGET_X_M = {
    'clear': 12.0,
    'stop': 0.0,
    'stand': 0.0,
    'park': 0.0,
    'traffic_conflict': 0.0,
    'law_direction': 0.0,
    'police_direction': 0.0,
    'device_direction': 0.0,
}


def command(case, frame, observed_x_m, observed_speed_mps):
    if case not in TARGET_X_M:
        raise ValueError('Unknown exact double-parking probe')
    if type(frame) is not int or not 0 <= frame < TOTAL_FRAMES:
        raise ValueError('Frame outside 30-second capture')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (observed_x_m, observed_speed_mps)) or observed_speed_mps < 0:
        raise ValueError('Original pose and speed required')
    remaining = TARGET_X_M[case] - observed_x_m
    if remaining < -1.0:
        raise ValueError('Subject overshot requested station')
    braking_distance = observed_speed_mps ** 2 / 4.0 + 1.5
    if remaining <= 0.5:
        return {'throttle': 0.0, 'brake': 1.0, 'steer': 0.0, 'phase': 'hold'}
    if remaining <= braking_distance:
        return {'throttle': 0.0, 'brake': 0.65, 'steer': 0.0, 'phase': 'brake'}
    return {'throttle': 0.22, 'brake': 0.0, 'steer': 0.0, 'phase': 'approach'}


def check():
    if TARGET_X_M['clear'] <= TARGET_X_M['park'] + 4.5:
        raise ValueError('Clear control would longitudinally overlap curbside car')
    if len(set(TARGET_X_M.values())) != 2:
        raise ValueError('Comparison should change only requested rest station')
    return {'case_count': len(TARGET_X_M), 'common_policy': True,
            'controller_targets_m': TARGET_X_M, 'legal_activity_inferred': False}
