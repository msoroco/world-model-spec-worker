"""Speed request and feedback policy for the two school-bus probes.

The CARLA runner must supply post-tick original velocity and retain its actual
control readbacks. Requests never stand in for realized speed or a legal result.
"""
import math

MPH_TO_MPS = 0.44704
REQUEST_MPH = {'probe_a': 52.0, 'probe_b': 58.0}


def request_mps(case_suffix):
    if case_suffix not in REQUEST_MPH:
        raise ValueError('Unknown case suffix')
    return REQUEST_MPH[case_suffix] * MPH_TO_MPS


def control(case_suffix, observed_velocity_mps, steer=0.0):
    if not isinstance(observed_velocity_mps, (list, tuple)) or len(observed_velocity_mps) != 3:
        raise ValueError('Need three original velocity components')
    if not all(type(v) in (int, float) and math.isfinite(v) for v in observed_velocity_mps):
        raise ValueError('Nonfinite original velocity')
    if type(steer) not in (int, float) or not math.isfinite(steer) or abs(steer) > 1:
        raise ValueError('Invalid steering request')
    speed = math.sqrt(sum(v * v for v in observed_velocity_mps))
    error = request_mps(case_suffix) - speed
    throttle = max(0.0, min(1.0, .18 * error))
    brake = max(0.0, min(1.0, -.22 * error))
    return {'throttle': throttle, 'brake': brake, 'steer': float(steer),
            'requested_speed_mps': request_mps(case_suffix),
            'observed_speed_mps': speed,
            'measurement_source': 'post_tick_original_velocity'}
