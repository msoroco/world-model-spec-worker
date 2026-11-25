"""Bounded ego control for the three selected officer exception constructions.

The approaching-hazard input is a reviewed source observation, never inferred
from an invented statutory distance or time threshold.
"""
import math
from officer_direction import behavior_suffix

PREFIX = 'testing__C157964__NRS-484B-257-2__motor_vehicle_driver__'
CASES = {'officer_controls_go', 'officer_controls_hold',
         'officer_present_inactive'}


def command(case_id, direction, *, other_inside, approaching_hazard,
            current_speed_mps, target_speed_mps=5.0):
    suffix = behavior_suffix(case_id)
    if type(other_inside) is not bool or type(approaching_hazard) is not bool:
        raise ValueError('Original other-body and approaching-hazard source required')
    for name, value in (('current speed', current_speed_mps),
                        ('target speed', target_speed_mps)):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Finite ' + name + ' required')
    if suffix == 'officer_controls_go':
        if direction not in ('stop', 'go'):
            raise ValueError('Active officer direction readback required')
        proceed = direction == 'go'
    elif suffix == 'officer_controls_hold':
        if direction != 'stop':
            raise ValueError('Hold case needs stop direction readback')
        proceed = False
    else:
        if direction != 'none':
            raise ValueError('Inactive comparison must not command officer control')
        proceed = not other_inside and not approaching_hazard
    if not proceed:
        return {'throttle': 0.0, 'brake': 1.0, 'proceed': False,
                'basis': 'officer hold' if suffix != 'officer_present_inactive'
                         else 'signed entrance and sourced other traffic'}
    error = target_speed_mps - current_speed_mps
    return {'throttle': min(0.6, max(0.0, 0.25 * error)),
            'brake': min(0.6, max(0.0, -0.25 * error)), 'proceed': True,
            'basis': 'programmed officer go' if suffix == 'officer_controls_go'
                     else 'signed entrance clear on supplied observation'}


def apply_native(carla, ego, selected):
    if not isinstance(selected, dict) or set(('throttle', 'brake', 'proceed')) - set(selected):
        raise ValueError('Selected ego command incomplete')
    control = carla.VehicleControl(throttle=selected['throttle'],
                                   brake=selected['brake'])
    ego.apply_control(control)
    return {'actor_id': ego.id, 'command': selected, 'native_control_applied': True}
