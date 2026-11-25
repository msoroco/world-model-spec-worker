"""Conservative engineering controller for a flashing-yellow-arrow turn."""
from __future__ import annotations
from math import hypot

class ControlError(ValueError):
    pass

def command(site, observation, policy):
    if policy not in ('yield_to_present','continue_when_clear'):
        raise ControlError('unknown policy')
    if str(observation.get('official_head_id'))!=str(site['official_head_id']) or observation.get('facing_approach_id')!=site['ego_approach_id']:
        raise ControlError('unbound official signal')
    aspects=observation.get('lit_aspects')
    if not isinstance(aspects,list) or 'flashing_yellow_turn_arrow' not in aspects:
        raise ControlError('flashing yellow turn arrow not observed')
    movement=observation.get('ego_movement')
    if not movement or (movement!=site['arrow_movement'] and
                        movement!=observation.get('concurrently_permitted_movement')):
        raise ControlError('movement unsupported by observed indications')
    concurrent = movement != site['arrow_movement']
    if concurrent and (not observation.get('concurrent_indications') or
                       not observation.get('concurrent_permission_source') or
                       not site.get('concurrent_route_xy')):
        raise ControlError('concurrent movement lacks original indication or route')
    if observation.get('frame') is None or observation.get('ego_xy') is None:
        raise ControlError('original frame and ego pose required')
    xy=observation['ego_xy']; stop=site['stop_line_xy']
    if hypot(xy[0]-stop[0],xy[1]-stop[1])>site['approach_control_radius_m']:
        return {'frame':observation['frame'],'throttle':site['approach_throttle'],'brake':0.0,'target':'approach'}
    users=observation.get('other_users')
    if not isinstance(users,list):
        raise ControlError('original participant packet required')
    occupied=any(u.get('region') in ('intersection','adjacent_crosswalk') for u in users)
    if policy=='yield_to_present' and occupied:
        return {'frame':observation['frame'],'throttle':0.0,'brake':site['yield_brake'],'target':'hold_before_entry'}
    return {'frame':observation['frame'],'throttle':site['turn_throttle'],'brake':0.0,
            'target':'concurrent_route' if concurrent else 'turn_route'}
