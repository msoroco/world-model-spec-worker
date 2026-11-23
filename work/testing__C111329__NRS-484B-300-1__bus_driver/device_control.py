"""Deterministic bus control contrast; targets are engineering intentions only."""
from __future__ import annotations

class ControlError(ValueError):
    pass

def command(site, observed, policy):
    if policy not in ('hold_red','enter_red','follow_police','proceed_when_green'):
        raise ControlError('unknown policy')
    if observed.get('device_id') != site['device_id'] or observed.get('facing_approach_id') != site['ego_approach_id']:
        raise ControlError('unbound governing device')
    required_aspect = 'green' if policy == 'proceed_when_green' else 'red'
    if observed.get('aspect') != required_aspect or observed.get('frame') is None:
        raise ControlError('original governing aspect and frame required')
    if observed.get('bus_front_signed_distance_m') is None:
        raise ControlError('original bus front distance required')
    if policy == 'follow_police':
        if observed.get('police_direction') != 'proceed' or not observed.get('police_direction_source'):
            raise ControlError('original contemporaneous police direction required')
    if policy == 'hold_red' or (policy == 'follow_police' and observed.get('police_direction') == 'stop'):
        return {'throttle':0.0,'brake':site['hold_brake'],'target':'remain_before_line','frame':observed['frame']}
    return {'throttle':site['proceed_throttle'],'brake':0.0,'target':'continue_surveyed_route','frame':observed['frame']}
