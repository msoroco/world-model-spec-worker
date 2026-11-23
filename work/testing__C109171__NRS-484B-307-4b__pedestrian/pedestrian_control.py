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


def target_control(case_suffix, site, position_xy, walker_control_factory, vector_factory, speed_mps=1.2):
    if case_suffix not in CASE_BEHAVIOR:
        raise ValueError('unknown exact pedestrian case')
    enter, _ = CASE_BEHAVIOR[case_suffix]
    if not 0 < speed_mps <= 2.5:
        raise ValueError('pedestrian speed outside controller envelope')
    route = site['pedestrian_route_xy']
    if len(route) < 3:
        raise ValueError('route requires sidewalk and highway waypoints')
    if not enter:
        return walker_control_factory(direction=vector_factory(0,0,0), speed=0.0, jump=False)
    x,y = map(float,position_xy)
    goal = None
    for pt in route[1:]:
        if math.hypot(float(pt[0])-x,float(pt[1])-y) > 0.25:
            goal=pt
            break
    if goal is None:
        return walker_control_factory(direction=vector_factory(0,0,0), speed=0.0, jump=False)
    dx,dy = float(goal[0])-x,float(goal[1])-y
    norm = math.hypot(dx,dy)
    return walker_control_factory(direction=vector_factory(dx/norm,dy/norm,0), speed=speed_mps, jump=False)


def apply_case(actor, case_suffix, site, walker_control_factory, vector_factory, speed_mps=1.2):
    location = actor.get_location()
    control = target_control(case_suffix,site,(location.x,location.y),walker_control_factory,vector_factory,speed_mps)
    actor.apply_control(control)
    return control
