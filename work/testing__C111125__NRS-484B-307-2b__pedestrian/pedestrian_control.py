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


class RouteFollower:
    """Advance through route waypoints without steering back to a passed point."""

    def __init__(self, case_suffix, site, control_factory, vector_factory,
                 speed_mps=1.2, arrival_m=0.35):
        if case_suffix not in ENTER_CASES | WAIT_CASES:
            raise ValueError('unknown exact case')
        if not 0 < speed_mps <= 2.5 or not 0 < arrival_m <= 1:
            raise ValueError('invalid pedestrian controller setting')
        self.case_suffix = case_suffix
        self.route = site['pedestrian_route_xy']
        if len(self.route) < 3:
            raise ValueError('route requires start, crossing and destination')
        self.control_factory = control_factory
        self.vector_factory = vector_factory
        self.speed_mps = speed_mps
        self.arrival_m = arrival_m
        self.next_index = 1

    def apply(self, actor):
        loc = actor.get_location()
        x, y = float(loc.x), float(loc.y)
        if self.case_suffix in WAIT_CASES:
            speed, direction = 0, self.vector_factory(0, 0, 0)
        else:
            while self.next_index < len(self.route):
                gx, gy = map(float, self.route[self.next_index])
                if math.hypot(gx - x, gy - y) > self.arrival_m:
                    break
                self.next_index += 1
            if self.next_index == len(self.route):
                speed, direction = 0, self.vector_factory(0, 0, 0)
            else:
                gx, gy = map(float, self.route[self.next_index])
                dx, dy = gx - x, gy - y
                distance = math.hypot(dx, dy)
                speed = self.speed_mps
                direction = self.vector_factory(dx / distance, dy / distance, 0)
        command = self.control_factory(direction=direction, speed=speed, jump=False)
        actor.apply_control(command)
        return command
