"""Source-gated construction for the four C24751 flashing-red encounters.

Requested stop positions are engineering targets. Original observations, not
controller targets, determine where the heavy vehicle actually stopped.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

ASSIGNMENT = 'testing__C24751__NRS-484B-310-1__heavy_vehicle_driver'


@dataclass(frozen=True)
class Case:
    suffix: str
    reference: str
    stop_offset_m: float


CASES = (
    Case('crosswalk_stop', 'crosswalk', -1.2),
    Case('crosswalk_late_stop', 'crosswalk', 0.8),
    Case('limit_line_stop', 'limit_line', -1.2),
    Case('intersection_stop', 'intersection', -1.2),
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and isfinite(value)


def validate_site(site):
    need(site.get('assignment_id') == ASSIGNMENT and site.get('cell_id') == 'C24751'
         and site.get('layout') == 'blind_intersection'
         and site.get('control') == 'flashing_red_signal',
         'reviewed site assignment or fixed cell differs')
    for name in ('map_sha256', 'approach_source_sha256', 'signal_identity_sha256',
                 'signal_geometry_sha256', 'signal_blueprint_sha256',
                 'occluder_identity_sha256', 'occluder_geometry_sha256',
                 'occluder_blueprint_sha256', 'ego_blueprint_sha256',
                 'camera_plan_sha256', 'stop_geometry_sha256'):
        need(bool(site.get(name)), name + ' source missing')
    need(site.get('signal_support') in ('map_object', 'spawned_prop'),
         'physical signal support missing')
    need(site.get('occluder_support') in ('map_object', 'spawned_prop'),
         'physical occluder support missing')
    need(site.get('official_device') is True and
         site.get('signal_approach_id') == site.get('approach_id') and
         bool(site.get('approach_id')), 'official signal governance missing')
    route = site.get('approach_waypoints')
    need(isinstance(route, list) and len(route) >= 2 and
         all(isinstance(p, list) and len(p) == 2 and all(finite(x) for x in p)
             for p in route), 'reviewed heavy-vehicle route missing')
    need(route[-1][0] > route[0][0], 'reviewed route reverses approach direction')
    need(finite(site.get('lane_width_m')) and finite(site.get('ego_width_m')) and
         0 < site['ego_width_m'] < site['lane_width_m'],
         'heavy vehicle does not fit reviewed lane')
    need(finite(site.get('ego_length_m')) and site['ego_length_m'] > 0,
         'heavy vehicle length missing')
    corners = site.get('occluder_corners_m')
    need(isinstance(corners, list) and len(corners) == 4 and
         all(isinstance(p, list) and len(p) == 2 and all(finite(x) for x in p)
             for p in corners), 'physical occluder polygon missing')
    need(len({p[0] for p in corners}) == 2 and len({p[1] for p in corners}) == 2,
         'occluder must have physical rectangular extent')
    refs = site.get('stop_references_m')
    need(isinstance(refs, dict) and finite(refs.get('intersection')),
         'surveyed intersection entry missing')
    for name in ('crosswalk', 'limit_line'):
        need(refs.get(name) is None or finite(refs[name]),
             'surveyed ' + name + ' reference invalid')


def reference(site, case):
    validate_site(site)
    need(case in CASES, 'unknown exact flashing-red case')
    refs = site['stop_references_m']
    if case.reference == 'crosswalk':
        need(refs['crosswalk'] is not None, 'crosswalk case missing physical reference')
        return refs['crosswalk']
    if case.reference == 'limit_line':
        need(refs['crosswalk'] is None and refs['limit_line'] is not None,
             'limit-line alternative requires no crosswalk and a marked line')
        return refs['limit_line']
    need(refs['crosswalk'] is None and refs['limit_line'] is None,
         'unmarked intersection alternative has another stop reference')
    return refs['intersection']


def build_case(adapter, site, case, engineering=None):
    """Create/read original CARLA actors; retain only locally owned actors."""
    stop_x = reference(site, case) + case.stop_offset_m
    engineering = engineering or {'approach_speed_mps': 2.0, 'braking_buffer_m': 1.0}
    need(finite(engineering.get('approach_speed_mps'))
         and engineering['approach_speed_mps'] > 0
         and finite(engineering.get('braking_buffer_m'))
         and engineering['braking_buffer_m'] >= 0,
         'reviewed controller tuning missing')
    owned = []
    try:
        if site['signal_support'] == 'spawned_prop':
            signal = adapter.spawn_signal(site['signal_geometry'],
                                          site['signal_blueprint_sha256'])
            need(signal is not None, 'official signal spawn failed')
            owned.append(signal)
        else:
            signal = adapter.lookup_signal(site['signal_identity_sha256'])
            need(signal is not None, 'mapped official signal missing')
        signal_check = adapter.read_signal(signal)
        need(signal_check.get('identity_sha256') == site['signal_identity_sha256']
             and signal_check.get('geometry_sha256') == site['signal_geometry_sha256']
             and signal_check.get('official_device') is True
             and signal_check.get('governed_approach_id') == site['approach_id'],
             'physical official signal readback differs')
        if site['occluder_support'] == 'spawned_prop':
            occluder = adapter.spawn_occluder(site['occluder_corners_m'],
                                              site['occluder_blueprint_sha256'])
            need(occluder is not None, 'physical occluder spawn failed')
            owned.append(occluder)
        else:
            occluder = adapter.lookup_occluder(site['occluder_identity_sha256'])
            need(occluder is not None, 'mapped physical occluder missing')
        occluder_check = adapter.read_occluder(occluder)
        need(occluder_check.get('identity_sha256') == site['occluder_identity_sha256']
             and occluder_check.get('geometry_sha256') == site['occluder_geometry_sha256']
             and occluder_check.get('physically_present') is True,
             'physical occluder readback differs')
        ego = adapter.spawn_heavy_vehicle(site['approach_waypoints'][0],
                                          site['ego_blueprint_sha256'])
        need(ego is not None, 'heavy vehicle spawn failed')
        owned.append(ego)
        vehicle_check = adapter.read_vehicle(ego)
        need(vehicle_check.get('actor_class') == 'heavy_vehicle'
             and vehicle_check.get('length_m') == site['ego_length_m']
             and vehicle_check.get('width_m') == site['ego_width_m'],
             'physical heavy vehicle dimensions differ')
        adapter.set_route(ego, site['approach_waypoints'])
        adapter.set_flashing_red(signal, site['approach_id'])
        adapter.set_controller_tuning(ego, engineering)
        adapter.set_stop_target(ego, stop_x)
        return {'ego': ego, 'signal': signal, 'occluder': occluder,
                'target_front_m': stop_x, 'reference_m': reference(site, case),
                'owned': tuple(owned)}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows, site, case):
    """Check original packet continuity and report measured stopping geometry."""
    reference_x = reference(site, case)
    need(len(rows) >= 3, 'original flashing-red history missing')
    first = rows[0].get('frame')
    need(type(first) is int, 'original first frame missing')
    fixed = {name: rows[0].get(name) for name in
             ('actor_id', 'signal_actor_id', 'occluder_actor_id', 'map_sha256',
              'signal_identity_sha256', 'occluder_identity_sha256',
              'stop_geometry_sha256', 'camera_plan_sha256', 'site_sha256',
              'frame_map_sha256')}
    need(all(fixed.values()), 'original source binding missing')
    for name in ('map_sha256', 'signal_identity_sha256', 'occluder_identity_sha256',
                 'stop_geometry_sha256', 'camera_plan_sha256'):
        need(fixed[name] == site[name], 'original source differs: ' + name)
    transitions = 0
    stopped = []
    for index, row in enumerate(rows):
        need(row.get('case_id') == ASSIGNMENT + '__' + case.suffix
             and row.get('frame') == first + index and finite(row.get('time_s'))
             and abs(row['time_s'] - index / 20) <= .002,
             'original frame or 20 Hz time join differs')
        need(all(row.get(name) == value for name, value in fixed.items()),
             'original source changed within history')
        need(row.get('signal_approach_id') == site['approach_id']
             and row.get('official_device') is True
             and row.get('signal_physically_present') is True
             and row.get('occluder_physically_present') is True,
             'original physical signal or occluder source missing')
        need(type(row.get('red_lit')) is bool and finite(row.get('front_m'))
             and finite(row.get('speed_mps')) and row['speed_mps'] >= 0,
             'original motion or flashing-red sample missing')
        if index:
            transitions += row['red_lit'] != rows[index - 1]['red_lit']
        if row['speed_mps'] == 0:
            stopped.append({'frame': row['frame'], 'front_m': row['front_m'],
                            'before_reference': row['front_m'] < reference_x})
    need(transitions >= 2 and any(row['red_lit'] for row in rows),
         'intermittent red illumination not observed')
    need(stopped, 'complete cessation absent from original history')
    return {'case_id': ASSIGNMENT + '__' + case.suffix,
            'frame_count': len(rows), 'reference_kind': case.reference,
            'surveyed_reference_m': reference_x, 'stop_observations': stopped,
            'flashing_red_transitions': transitions, 'source_identity': fixed,
            'post_stop_right_to_proceed': 'unresolved_applicable_rules',
            'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
