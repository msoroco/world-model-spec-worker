"""Engineering control for the straight green case family.

This controller creates a controlled trajectory contrast. Its conflict-zone
policy is conservative engineering, not a statutory right-of-way adjudication.
"""
from __future__ import annotations
from math import hypot

class ControlError(ValueError):
    pass

def command(site, observation, policy):
    if policy not in ('proceed_when_clear','yield_to_present'):
        raise ControlError('unknown policy')
    if observation.get('official_head_id') != site['official_head_id'] or observation.get('facing_approach_id') != site['ego_approach_id']:
        raise ControlError('unbound governing signal')
    if observation.get('lit_aspects') != ['circular_green']:
        raise ControlError('sole circular green not observed')
    if observation.get('frame') is None or observation.get('ego_xy') is None:
        raise ControlError('original frame and ego pose required')
    stop=site['stop_line_xy']
    xy=observation['ego_xy']
    distance=hypot(xy[0]-stop[0],xy[1]-stop[1])
    if distance > site['approach_control_radius_m']:
        return {'throttle':site['approach_throttle'],'brake':0.0,'target':'approach','frame':observation['frame']}
    conflicts=observation.get('other_users')
    if not isinstance(conflicts,list):
        raise ControlError('original other-user packet required')
    occupied=any(u.get('region') in ('intersection','adjacent_crosswalk') for u in conflicts)
    if policy=='yield_to_present' and occupied:
        return {'throttle':0.0,'brake':site['yield_brake'],'target':'hold_before_entry','frame':observation['frame']}
    return {'throttle':site['proceed_throttle'],'brake':0.0,'target':'straight_route','frame':observation['frame']}
