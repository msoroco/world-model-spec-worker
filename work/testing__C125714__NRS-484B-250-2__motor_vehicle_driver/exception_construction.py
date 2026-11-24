"""Source-gated construction for the NRS 484B.250(5) fact patterns.

This is an engineering constructor. Reviewed authority and original motion must
still establish whether an exception applies in a physical recording.
"""
from __future__ import annotations

import hashlib
import math

BASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver__'
KINDS = {
    'official_device_controlled': 'device',
    'opposite_intends_left': 'intends',
    'opposite_makes_left': 'makes',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def route_points(route, name):
    require(isinstance(route, list) and len(route) >= 3 and all(
        isinstance(point, list) and len(point) == 3 and all(
            type(value) in (int, float) and math.isfinite(value)
            for value in point) for point in route),
        name + ' source-reviewed route missing')
    require(math.dist(route[0], route[-1]) > 10,
            name + ' route does not traverse the intersection')


def heading(route, start, end):
    vector = (route[end][0] - route[start][0],
              route[end][1] - route[start][1])
    length = math.hypot(*vector)
    require(length > 2, 'degenerate exception route heading')
    return (vector[0] / length, vector[1] / length)


def construct(adapter, site, case):
    """Create two read-back checked actors after authority and geometry checks."""
    case_id = case.get('case_id', '')
    kind = case_id.removeprefix(BASE)
    require(case_id == site.get('case_id') and case_id.startswith(BASE) and
            kind in KINDS and site.get('assignment_id') == BASE[:-2] and
            site.get('cell_id') == 'C125714', 'wrong exception case identity')
    road = adapter.map_opendrive_bytes()
    require(isinstance(road, bytes) and
            hashlib.sha256(road).hexdigest() == site.get('map_sha256'),
            'live map differs from reviewed exception map')
    for key in ('reviewer', 'map_source_citation', 'highway_source_citation',
                'device_source_citation', 'crossing_id', 'roadway_id',
                'ego_blueprint_sha256', 'other_blueprint_sha256'):
        require(isinstance(site.get(key), str) and bool(site[key]),
                'reviewed exception source missing: ' + key)
    require(site.get('subsection_4_context_reviewed') is True,
            'subsection-4 qualification is unreviewed')
    require(type(site.get('official_device_controls_intersection')) is bool,
            'official-device authority is unreviewed')
    for name in ('ego', 'other'):
        route_points(site.get(name + '_route_xyz_m'), name)
        require(adapter.route_enters_crossing(site[name + '_route_xyz_m'],
                site['crossing_id'], site[name + '_highway']) is True,
                name + ' route misses the reviewed intersection')
    if kind == 'official_device_controlled':
        require(site.get('approach_relation') == 'crossing' and
                site.get('ego_highway') != site.get('other_highway') and
                site.get('ego_side') == 'left' and
                site.get('other_side') == 'right',
                'device case must retain different-highway left/right crossing')
        require(site['official_device_controls_intersection'] is True and
                isinstance(site.get('official_device_id'), str) and
                bool(site['official_device_id']) and
                adapter.device_controls_intersection(site['official_device_id'],
                                                     site['crossing_id']) is True,
                'official device does not control reviewed intersection')
    else:
        require(site.get('approach_relation') == 'opposite' and
                site.get('ego_highway') == site.get('other_highway') and
                site['official_device_controls_intersection'] is False,
                'opposite ungoverned approach geometry required')
        ego_heading = heading(site['ego_route_xyz_m'], 0, 1)
        other_heading = heading(site['other_route_xyz_m'], 0, 1)
        require(sum(a*b for a, b in zip(ego_heading, other_heading)) < -0.8,
                'source-reviewed approach routes are not opposite')
        require(site.get('other_left_turn_intent') is True and
                isinstance(site.get('turn_source_citation'), str) and
                bool(site['turn_source_citation']),
                'source-reviewed left-turn intent missing')
        if kind == 'opposite_makes_left':
            exit_heading = heading(site['other_route_xyz_m'], 1, 2)
            require(other_heading[0]*exit_heading[1] -
                    other_heading[1]*exit_heading[0] > 0.7,
                    'original route geometry does not make a left turn')
            require(site.get('other_left_turn_making') is True and
                    adapter.route_makes_left_turn(site['other_route_xyz_m'],
                                                   site['crossing_id']) is True,
                    'realizable left-turn route missing')
        else:
            require(site.get('other_left_turn_making') is False,
                    'intent-only case cannot already assert making left turn')
    owned = []
    try:
        actors = {}
        for name in ('ego', 'other'):
            actor = adapter.spawn_vehicle(site[name + '_route_xyz_m'][0],
                                          blueprint_sha256=site[name + '_blueprint_sha256'])
            require(actor is not None and actor.is_alive,
                    name + ' exception vehicle spawn failed')
            actors[name] = actor
            owned.append(actor)
        require(actors['ego'].id != actors['other'].id,
                'exception vehicle identities collide')
        for name in ('ego', 'other'):
            adapter.set_vehicle_route(actors[name], site[name + '_route_xyz_m'])
            require(adapter.vehicle_route_readback(
                actors[name], site[name + '_route_xyz_m']) is True,
                name + ' exception route readback differs')
        return {'actors': actors, 'owned': tuple(owned),
                'exception_fact_pattern': kind, 'legal_exception_applies': 'unresolved'}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
