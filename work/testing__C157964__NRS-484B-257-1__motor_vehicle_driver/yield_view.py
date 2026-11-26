"""Nearest-view yield-sign construction and source-bound motion audit.

Physical reference, approach speed and through-vehicle phases are measured.
Immediate hazard, right-of-way and governing-control applicability remain review.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    approach_policy: str
    through_state: str
    officer_controls: bool = False


CASES = (
    Case('yield_slow_approaching', 'slow', 'approaching'),
    Case('yield_stop_approaching', 'stop', 'approaching'),
    Case('yield_slow_occupied', 'slow', 'occupied'),
    Case('officer_controlling', 'slow', 'approaching', True),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def validate_site(site: Mapping, case: Case):
    require(case in CASES, 'unknown exact yield case')
    require(site.get('cell_id') == 'C157964' and site.get('actor') == 'motor_vehicle_driver',
            'wrong exact cell or actor')
    require(site.get('yield_sign_present') is True and
            site.get('stop_line_present') is False and
            site.get('near_crosswalk_present') is False,
            'nearest-view reference hierarchy not established')
    for key in ('jurisdiction', 'yield_sign', 'stop_line_absence', 'crosswalk_absence',
                'nearest_view_location', 'through_highway', 'sight_observation',
                'officer_control', 'traffic_signal_control', 'ego_vehicle'):
        require(site.get(key + '_source_sha256'), 'original site source missing: ' + key)
    require(site.get('officer_controls') is case.officer_controls and
            site.get('signal_controls') is False, 'governing-control context differs')
    require(number(site.get('nearest_view_station_m')) and
            number(site.get('physical_reference_station_m')),
            'nearest-view and physical reference missing')
    route = site.get('route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and all(number(x) for x in p)
                for p in route), 'supported approach route missing')
    return {'reference_hierarchy': 'neither_line_nor_crosswalk_nearest_view',
            'nearest_view_station_m': site['nearest_view_station_m'],
            'governing_control_exception_context': case.officer_controls,
            'legal_judgment': None}


def construct(adapter, site: Mapping, case: Case):
    context = validate_site(site, case)
    owned = []
    try:
        ego = adapter.spawn_vehicle(site['route_xy'][0], 'ego')
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        through = adapter.spawn_vehicle(site['through_spawn_xy'], 'through')
        require(through is not None, 'through spawn failed')
        owned.append(through)
        adapter.set_yield_approach(ego, site['route_xy'],
                                   site['nearest_view_station_m'], case.approach_policy)
        adapter.set_through_phase(through, case.through_state)
        adapter.set_officer_control(case.officer_controls)
        return {'case_id': case.case_id, 'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], site: Mapping, case: Case):
    validate_site(site, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    start = rows[0].get('original_frame')
    require(type(start) is int, 'original frame identity missing')
    ego_id = through_id = None
    speeds = []
    crossings = []
    through_stations = []
    reference_events = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == start + i and number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for key in ('source', 'ego_motion', 'through_motion', 'body_geometry',
                    'reference', 'sight', 'control'):
            require(row.get(key + '_sha256'), 'original source missing: ' + key)
        require(row.get('reference_source_sha256') == site['nearest_view_location_source_sha256'] and
                row.get('officer_controls') is case.officer_controls and
                row.get('signal_controls') is False and
                row.get('stop_line_present') is False and
                row.get('near_crosswalk_present') is False,
                'original reference/control context changed')
        require(row.get('ego_id') and row.get('through_id'), 'participant identity missing')
        ego_id = ego_id or row['ego_id']
        through_id = through_id or row['through_id']
        require(row['ego_id'] == ego_id and row['through_id'] == through_id and
                ego_id != through_id, 'participant identity changed')
        for key in ('ego_speed_mps', 'through_center_station_m',
                    'through_min_vertex_station_m', 'ego_leading_station_m'):
            require(number(row.get(key)), 'original numeric stream missing: ' + key)
        require(row.get('through_phase') == case.through_state,
                'through vehicle phase differs from case')
        require(type(row.get('ego_across_or_within')) is bool,
                'intersection crossing history missing')
        require(type(row.get('all_at_reference_observed')) is bool,
                'original all-at-reference event missing')
        if row['all_at_reference_observed']:
            reference_events.append(i)
        speeds.append(row['ego_speed_mps'])
        through_stations.append(row['through_center_station_m'])
        if row['ego_leading_station_m'] >= site['physical_reference_station_m']:
            crossings.append(i)
    require(crossings, 'physical reference never crossed')
    first_cross = crossings[0]
    require(len(reference_events) == 1 and reference_events[0] <= first_cross,
            'one observed all-at-reference event before crossing required')
    reference_index = reference_events[0]
    require(first_cross > 0 and rows[first_cross - 1]['ego_leading_station_m'] <
            site['physical_reference_station_m'], 'first physical crossing invalid')
    approach_min = min(speeds[:first_cross + 1])
    if case.approach_policy == 'stop':
        require(any(value <= .1 for value in speeds[:first_cross]), 'observed stop absent')
    else:
        require(approach_min < max(speeds[:first_cross + 1]), 'observed slowing absent')
    require(any(r['ego_across_or_within'] for r in rows[first_cross:]),
            'across-or-within history missing')
    return {'case_id': case.case_id, 'frame_count': 900,
            'first_physical_reference_crossing_frame': start + first_cross,
            'minimum_original_approach_speed_mps': approach_min,
            'through_center_station_at_crossing_m': through_stations[first_cross],
            'through_center_station_at_all_reference_m': through_stations[reference_index],
            'through_min_vertex_station_at_all_reference_m': rows[reference_index]['through_min_vertex_station_m'],
            'all_at_reference_original_frame': start + reference_index,
            'through_min_vertex_station_at_crossing_m': rows[first_cross]['through_min_vertex_station_m'],
            'officer_controls_observed': case.officer_controls,
            'immediate_hazard_judgment': None, 'right_of_way_judgment': None,
            'governing_control_exception_judgment': None, 'legal_judgment': None}
