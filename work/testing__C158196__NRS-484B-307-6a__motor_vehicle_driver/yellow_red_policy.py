"""Portable 20 Hz signal and approach policy for the exact yellow/red cases.

This schedules a reproducible warning transition. Real signal-head governance,
body entry and visibility must be read from retained Native sources afterward.
"""
import math

RATE_HZ = 20
DURATION_FRAMES = 900
YELLOW_START = 100
RED_START = 160
CASES = {
    'entry_before_red': 150,
    'entry_at_red': 160,
    'entry_after_red': 170,
    'stops_on_yellow': None,
}


def signal_state(frame):
    if not isinstance(frame, int) or isinstance(frame, bool) or not 0 <= frame < DURATION_FRAMES:
        raise ValueError('Frame outside authored signal schedule')
    if frame < YELLOW_START:
        return 'Green'
    if frame < RED_START:
        return 'Yellow'
    return 'Red'


def approach_control(case, frame, distance_to_boundary_m, speed_mps):
    """Return bounded steering-free control from observed distance and speed.

    The target frame is a construction target, not an observed entry. The
    finalizer must reject an attempt whose sourced entry timing differs.
    """
    if case not in CASES:
        raise ValueError('Unknown selected red-entry case')
    signal_state(frame)
    for value in (distance_to_boundary_m, speed_mps):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError('Finite Native distance and speed required')
    if speed_mps < 0:
        raise ValueError('Negative approach speed')
    if case == 'stops_on_yellow':
        target_speed = 0.0 if frame >= YELLOW_START else min(8.0, max(0.0, distance_to_boundary_m / 5.0))
    else:
        remaining_s = max((CASES[case] - frame) / RATE_HZ, 0.05)
        target_speed = min(12.0, max(0.0, distance_to_boundary_m / remaining_s))
    error = target_speed - speed_mps
    return {'signal_state': signal_state(frame), 'target_speed_mps': target_speed,
            'throttle': min(0.65, max(0.0, 0.25 * error)),
            'brake': min(0.9, max(0.0, -0.35 * error)), 'steer': 0.0,
            'target_entry_frame': CASES[case], 'observed_entry': 'unverified'}


def apply_step(signal, actor, carla, case, frame, distance_to_boundary_m, speed_mps):
    """Issue one frame of Native commands; caller owns ticking and source capture."""
    command = approach_control(case, frame, distance_to_boundary_m, speed_mps)
    signal.set_state(getattr(carla.TrafficLightState, command['signal_state']))
    signal.freeze(True)
    actor.apply_control(carla.VehicleControl(throttle=command['throttle'],
                                             brake=command['brake'], steer=command['steer']))
    return command
