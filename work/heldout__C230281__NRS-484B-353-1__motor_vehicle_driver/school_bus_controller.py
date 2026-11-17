"""Construction control targets for the eight selected school-bus cases."""
from __future__ import annotations

BRANCHES = {
    'meeting_stop', 'meeting_restart_before_red_ceases', 'meeting_pass_red',
    'overtaking_stop', 'overtaking_pass_red',
    'meeting_divided_other_roadway_pass', 'meeting_officer_controlled_pass',
    'meeting_resume_after_red_ceases',
}
PASS_DURING_RED = {
    'meeting_pass_red', 'overtaking_pass_red',
    'meeting_divided_other_roadway_pass', 'meeting_officer_controlled_pass',
}


def target(branch, *, red_signal_operating, stop_observed):
    """Prescribe scenario motion; source measurements decide what occurred."""
    if branch not in BRANCHES or type(red_signal_operating) is not bool or type(stop_observed) is not bool:
        raise ValueError('Unknown school-bus branch or signal/stop state')
    if branch == 'meeting_restart_before_red_ceases':
        speed = 5.0 if (stop_observed or not red_signal_operating) else 0.0
    elif branch in PASS_DURING_RED or not red_signal_operating:
        speed = 5.0
    else:
        speed = 0.0
    return {'branch': branch, 'target_speed_mps': speed,
            'red_signal_operating': red_signal_operating,
            'construction_only': True, 'legal_conclusion': None}


def apply(vehicle, control_type, command, *, speed_mps):
    if (not isinstance(command, dict) or command.get('branch') not in BRANCHES or
        type(speed_mps) not in (int, float) or speed_mps < 0):
        raise ValueError('Invalid school-bus vehicle/control state')
    error = command['target_speed_mps'] - speed_mps
    throttle = min(0.65, max(0.0, 0.20*error))
    brake = min(1.0, max(0.0, -0.35*error))
    output = control_type(throttle=throttle, brake=brake, steer=0.0)
    vehicle.apply_control(output)
    return output
