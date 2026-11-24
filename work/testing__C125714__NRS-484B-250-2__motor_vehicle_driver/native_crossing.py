"""Lazy two-vehicle construction for the reviewed C125714 crossing.

The Native adapter owns the physics calls. This module checks that both actual
routes reach the same reviewed intersection before spawning anything.
"""
from __future__ import annotations

import hashlib
import math


CASE_SUFFIXES = ('timing_below_training', 'timing_inside_training',
                 'timing_above_training', 'yield_wait_for_other_clear',
                 'advance_at_release')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def points(route, name):
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 3 and
                all(type(v) in (int, float) and math.isfinite(v) for v in p)
                for p in route), name + ' original 3D route missing')
    require(math.dist(route[0], route[-1]) > 5.0,
            name + ' route does not travel through crossing')


def construct(adapter, site, case):
    """Construct and read back both participants, rolling back owned actors."""
    require(site.get('assignment_id') ==
            'testing__C125714__NRS-484B-250-2__motor_vehicle_driver' and
            site.get('cell_id') == 'C125714', 'wrong assignment/cell')
    require(case.get('case_id') == site.get('case_id') and
            case['case_id'].endswith(CASE_SUFFIXES) and
            type(case.get('requested_entry_offset_s')) in (int, float) and
            math.isfinite(case['requested_entry_offset_s']),
            'exact case or finite timing request missing')
    road = adapter.map_opendrive_bytes()
    require(isinstance(road, bytes) and
            hashlib.sha256(road).hexdigest() == site.get('map_sha256'),
            'live map differs from reviewed original map')
    for key in ('map_source_citation', 'highway_source_citation',
                'device_source_citation', 'crossing_id', 'roadway_id',
                'ego_blueprint_sha256', 'other_blueprint_sha256'):
        require(bool(site.get(key)), 'reviewed construction source missing: ' + key)
    require(site.get('approach_relation') == 'crossing' and
            site.get('ego_highway') != site.get('other_highway') and
            site.get('ego_side') == 'left' and site.get('other_side') == 'right',
            'left/right different-highway crossing not established')
    require(site.get('official_device_controls_intersection') is False and
            site.get('other_left_turn_intent') is False and
            site.get('subsection_4_context_reviewed') is True,
            'exception context not source reviewed for selected branch')
    for name in ('ego', 'other'):
        route = site.get(name + '_route_xyz_m')
        points(route, name)
        require(adapter.route_enters_crossing(route, site['crossing_id'],
                                              site[name + '_highway']) is True,
                name + ' route does not enter same reviewed crossing')
    owned = []
    try:
        actors = {}
        for name in ('ego', 'other'):
            actor = adapter.spawn_vehicle(site[name + '_route_xyz_m'][0],
                                          blueprint_sha256=site[name + '_blueprint_sha256'])
            require(actor is not None and actor.is_alive,
                    name + ' vehicle spawn failed')
            actors[name] = actor
            owned.append(actor)
        require(actors['ego'].id != actors['other'].id,
                'original vehicle identity collision')
        for name in ('ego', 'other'):
            adapter.set_vehicle_route(actors[name], site[name + '_route_xyz_m'])
            require(adapter.vehicle_route_readback(actors[name],
                    site[name + '_route_xyz_m']) is True,
                    name + ' original route readback differs')
        return {'actors': actors, 'owned': tuple(owned),
                'requested_entry_offset_s': case['requested_entry_offset_s']}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def apply_timing(adapter, actors, original_elapsed_s, case, schedule):
    """Apply a reviewed launch schedule; do not claim its requested offset occurred."""
    require(type(original_elapsed_s) in (int, float) and math.isfinite(original_elapsed_s),
            'original Native clock missing')
    require(set(schedule) == {'ego_release_s', 'other_release_s'} and
            all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                for value in schedule.values()), 'reviewed release schedule missing')
    require(abs((schedule['ego_release_s'] - schedule['other_release_s']) -
                case['requested_entry_offset_s']) <= .05,
            'release schedule differs from requested timing target')
    for name in ('ego', 'other'):
        adapter.apply_vehicle_control(actors[name],
            throttle=.35 if original_elapsed_s >= schedule[name + '_release_s'] else 0.0,
            brake=0.0 if original_elapsed_s >= schedule[name + '_release_s'] else 1.0)
