"""Portable pedestrian route controller for the four exact entry attempts.

The intended behavior is an authored test target, never a claim about a recorded
pedestrian or permission. Native finalization reads the original device source.
"""
from __future__ import annotations
import math

CASE_BEHAVIOR = {
    'arrow_wait': (False, False),
    'arrow_early_entry': (True, False),
    'arrow_walk_entry': (True, True),
    'arrow_walk_wait': (False, True),
}


class RouteFollower:
    """Retain progress along one authored route during a Native attempt.

    The follower requests motion only. Captured position and signal packets,
    rather than this controller, establish whether highway entry happened.
    """

    def __init__(self, case_suffix, site, speed_mps=1.2, reach_m=0.25):
        if case_suffix not in CASE_BEHAVIOR:
            raise ValueError('unknown exact pedestrian case')
        if not 0 < speed_mps <= 2.5 or not 0 < reach_m <= 1:
            raise ValueError('invalid pedestrian controller envelope')
        route = site['pedestrian_route_xy']
        if len(route) < 3:
            raise ValueError('route requires sidewalk and highway waypoints')
        if any(len(point) != 2 or not all(math.isfinite(float(v)) for v in point) for point in route):
            raise ValueError('route contains nonfinite coordinate')
        self.case_suffix = case_suffix
        self.route = route
        self.speed_mps = speed_mps
        self.reach_m = reach_m
        self.next_index = 1

    def control(self, position_xy, walker_control_factory, vector_factory):
        x, y = map(float, position_xy)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('nonfinite walker position')
        if not CASE_BEHAVIOR[self.case_suffix][0]:
            return walker_control_factory(direction=vector_factory(0,0,0), speed=0.0, jump=False)
        while self.next_index < len(self.route):
            goal = self.route[self.next_index]
            dx, dy = float(goal[0])-x, float(goal[1])-y
            distance = math.hypot(dx, dy)
            if distance > self.reach_m:
                return walker_control_factory(direction=vector_factory(dx/distance,dy/distance,0),
                                              speed=self.speed_mps,jump=False)
            self.next_index += 1
        return walker_control_factory(direction=vector_factory(0,0,0), speed=0.0, jump=False)

    def apply(self, actor, walker_control_factory, vector_factory):
        location = actor.get_location()
        control = self.control((location.x, location.y), walker_control_factory, vector_factory)
        actor.apply_control(control)
        return control


def target_control(case_suffix, site, position_xy, walker_control_factory, vector_factory, speed_mps=1.2):
    """Single-step convenience API; live loops should retain RouteFollower."""
    return RouteFollower(case_suffix, site, speed_mps).control(position_xy, walker_control_factory, vector_factory)


def apply_case(actor, case_suffix, site, walker_control_factory, vector_factory, speed_mps=1.2):
    location = actor.get_location()
    control = target_control(case_suffix,site,(location.x,location.y),walker_control_factory,vector_factory,speed_mps)
    actor.apply_control(control)
    return control
