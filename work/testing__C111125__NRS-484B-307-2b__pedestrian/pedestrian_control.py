"""Portable authored pedestrian route control; observed movement is measured later."""
from __future__ import annotations
import math

ENTER_CASES = {'marked_cross', 'unmarked_cross', 'other_device_cross', 'outside_cross'}
WAIT_CASES = {'other_device_stop'}


def target_control(case_suffix, site, position_xy, control_factory, vector_factory, speed_mps=1.2):
    if case_suffix not in ENTER_CASES | WAIT_CASES:
        raise ValueError('unknown exact case')
    if not 0 < speed_mps <= 2.5:
        raise ValueError('speed outside authored pedestrian envelope')
    if case_suffix in WAIT_CASES:
        return control_factory(direction=vector_factory(0, 0, 0), speed=0, jump=False)
    x, y = map(float, position_xy)
    for goal in site['pedestrian_route_xy'][1:]:
        dx, dy = float(goal[0])-x, float(goal[1])-y
        norm = math.hypot(dx, dy)
        if norm > 0.25:
            return control_factory(direction=vector_factory(dx/norm, dy/norm, 0), speed=speed_mps, jump=False)
    return control_factory(direction=vector_factory(0, 0, 0), speed=0, jump=False)


def apply_case(actor, case_suffix, site, control_factory, vector_factory, speed_mps=1.2):
    loc = actor.get_location()
    command = target_control(case_suffix, site, (loc.x, loc.y), control_factory, vector_factory, speed_mps)
    actor.apply_control(command)
    return command
