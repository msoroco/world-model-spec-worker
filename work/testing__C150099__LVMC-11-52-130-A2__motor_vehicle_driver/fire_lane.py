"""Source-gated fire-lane construction and original-frame observation.

Commands and geometric measurements are not legal conclusions. The City Fire Code
posting/designation facts require independent location-specific source records.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Mapping

CELL = 'C150099'
LAW = 'LVMC-11-52-130-A2'

@dataclass(frozen=True)
class Case:
    id: str
    activity: str
    attended: bool
    property_kind: str
    target_region: str = 'inside'
    exception: str = 'none'

CASES = (
    Case('public_park_attended', 'park', True, 'public'),
    Case('public_park_unattended', 'park', False, 'public'),
    Case('private_park_attended', 'park', True, 'private'),
    Case('private_park_unattended', 'park', False, 'private'),
    Case('public_stop', 'stop', True, 'public'),
    Case('public_stand', 'stand', True, 'public'),
    Case('outside_posted_extent', 'park', True, 'public', 'outside'),
    Case('traffic_conflict_exception', 'stop', True, 'public', 'inside', 'lawful_traffic_conflict'),
    Case('police_direction_exception', 'stop', True, 'public', 'inside', 'police_direction'),
    Case('device_direction_exception', 'stop', True, 'public', 'inside', 'traffic_device_direction'),
)


def require(value: bool, reason: str) -> None:
    if not value:
        raise ValueError(reason)


def number(value, name: str) -> float:
    require(type(value) in (int, float) and isfinite(value), f'{name} invalid')
    return float(value)


def validate_site(site: Mapping, case: Case) -> None:
    require(case in CASES, 'unknown case')
    require(site.get('cell_id') == CELL and site.get('layout') == 'one_way_road', 'wrong cell or layout')
    require(site.get('property_kind') == case.property_kind, 'property context mismatch')
    for key in ('map_sha256', 'jurisdiction_sha256', 'fire_code_designation_sha256',
                'posting_authority_sha256', 'posted_extent_sha256', 'sign_identity_sha256',
                'sign_appearance_sha256', 'curb_geometry_sha256', 'property_source_sha256',
                'one_way_source_sha256', 'ego_blueprint_sha256', 'camera_plan_sha256'):
        require(bool(site.get(key)), f'{key} source missing')
    require(site.get('sign_support') in ('map_object', 'spawned_prop'), 'sign support missing')
    require(site.get('sign_text') == 'FIRE LANE', 'fire lane sign text mismatch')
    bounds = site.get('posted_interval_m')
    require(isinstance(bounds, list) and len(bounds) == 2, 'posted extent missing')
    lo, hi = (number(v, 'posted boundary') for v in bounds)
    require(hi > lo, 'posted extent invalid')
    curb = number(site.get('curb_y_m'), 'curb')
    route = site.get('approach_waypoints')
    require(isinstance(route, list) and len(route) >= 2, 'approach route missing')
    require(all(isinstance(p, list) and len(p) == 2 and all(type(v) in (int, float) and isfinite(v) for v in p) for p in route), 'approach route invalid')
    require(route[0][0] < route[-1][0], 'one-way route reversed')
    require(isfinite(curb), 'curb invalid')
    if case.exception != 'none':
        key = {'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
               'police_direction': 'police_direction_source_sha256',
               'traffic_device_direction': 'traffic_device_source_sha256'}[case.exception]
        require(bool(site.get(key)), f'{key} missing')


def target_interval(site: Mapping, case: Case, body_length_m: float) -> tuple[float, float]:
    length = number(body_length_m, 'body length')
    require(length > 0, 'body length invalid')
    lo, hi = site['posted_interval_m']
    require(hi - lo > length + 1, 'posted extent too short for body')
    if case.target_region == 'inside':
        center = (lo + hi) / 2
    else:
        center = hi + length / 2 + 1
    return center - length / 2, center + length / 2


def build_case(adapter, site: Mapping, case: Case, body_length_m: float) -> dict:
    """Construct sign and ego, read back physical sign, clean owned actors on failure."""
    validate_site(site, case)
    interval = target_interval(site, case, body_length_m)
    owned = []
    try:
        if site['sign_support'] == 'spawned_prop':
            sign = adapter.spawn_sign(site['sign_text'], site['posted_interval_m'], site['curb_y_m'])
            require(sign is not None, 'sign spawn failed')
            owned.append(sign)
        else:
            sign = adapter.lookup_sign(site['sign_identity_sha256'])
            require(sign is not None, 'mapped sign missing')
        readback = adapter.read_sign(sign)
        require(readback.get('identity_sha256') == site['sign_identity_sha256'], 'sign identity mismatch')
        require(readback.get('appearance_sha256') == site['sign_appearance_sha256'], 'sign appearance mismatch')
        require(readback.get('physically_present') is True, 'sign physical presence missing')
        ego = adapter.spawn_vehicle(site['approach_waypoints'][0], site['ego_blueprint_sha256'])
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        adapter.set_route(ego, site['approach_waypoints'], one_way=True)
        adapter.set_curb_target(ego, interval, site['curb_y_m'], activity=case.activity)
        adapter.set_attendance(ego, case.attended)
        if case.exception != 'none':
            adapter.set_exception(ego, case.exception)
        return {'case_id': case.id, 'ego': ego, 'sign': sign,
                'commanded_body_interval_m': interval, 'owned': tuple(owned)}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original_history(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    validate_site(site, case)
    require(len(rows) >= 2, 'original history missing')
    fixed = {k: rows[0].get(k) for k in ('ego_id', 'sign_id', 'map_sha256',
             'jurisdiction_sha256', 'fire_code_designation_sha256',
             'posting_authority_sha256', 'posted_extent_sha256', 'sign_identity_sha256',
             'sign_appearance_sha256', 'curb_geometry_sha256', 'property_source_sha256',
             'camera_plan_sha256', 'frame_map_sha256')}
    require(all(fixed.values()), 'fixed original source missing')
    require(all(fixed[k] == site[k] for k in fixed if k not in ('ego_id', 'sign_id', 'frame_map_sha256')), 'site source mismatch')
    first = rows[0].get('original_frame')
    require(type(first) is int, 'original frame missing')
    lo, hi = site['posted_interval_m']
    output = []
    previous_time = None
    for i, row in enumerate(rows):
        require(row.get('case_id') == case.id and row.get('original_frame') == first + i, 'original frame join mismatch')
        require(all(row.get(k) == v for k, v in fixed.items()), 'fixed source changed')
        require(row.get('source_sha256') and row.get('body_footprint_source_sha256'), 'body source missing')
        require(row.get('sign_physically_present') is True, 'sign readback missing')
        west, east = number(row.get('body_west_x_m'), 'body west'), number(row.get('body_east_x_m'), 'body east')
        require(east > west, 'body footprint invalid')
        curb_gap = number(row.get('body_curb_gap_m'), 'curb gap')
        require(curb_gap >= 0, 'curb gap invalid')
        time_s = number(row.get('time_s'), 'time')
        if previous_time is not None:
            require(0.049 <= time_s - previous_time <= 0.051, '20 Hz time join mismatch')
        previous_time = time_s
        require(row.get('activity_observation') in ('moving', 'stopped', 'standing', 'parked'), 'activity missing')
        require(type(row.get('attended_observation')) is bool, 'attendance missing')
        require(row.get('property_kind') == case.property_kind, 'property observation changed')
        if case.exception != 'none':
            require(row.get('exception_kind') == case.exception and row.get('exception_source_sha256'), 'exception source missing')
        else:
            require(row.get('exception_kind') == 'none', 'unexpected exception')
        overlap = max(0.0, min(east, hi) - max(west, lo))
        output.append({'original_frame': first + i, 'time_s': time_s,
                       'overlap_posted_interval_m': overlap, 'curb_gap_m': curb_gap,
                       'activity': row['activity_observation'],
                       'attended': row['attended_observation']})
    return {'case_id': case.id, 'frame_count': len(rows), 'source_identity': fixed,
            'first_original_frame': first, 'last_original_frame': first + len(rows) - 1,
            'overlap_frames': sum(o['overlap_posted_interval_m'] > 0 for o in output),
            'observations': output, 'legal_judgment': None,
            'physical_visibility_verified': False}


def audit_comparison(left: Mapping, right: Mapping, difference: str) -> None:
    require(left.get('case_id') != right.get('case_id'), 'same case compared')
    require(difference in ('attended', 'property_kind', 'activity', 'target_region', 'exception'), 'difference invalid')
    for side in (left, right):
        require(side.get('frame_count') == 900 and side.get('original_history_sha256') and side.get('camera_plan_sha256'), 'comparison source missing')
        require(isinstance(side.get('fixed_sources'), dict), 'fixed sources missing')
    for key in ('map_sha256', 'jurisdiction_sha256', 'fire_code_designation_sha256',
                'posting_authority_sha256', 'sign_identity_sha256', 'sign_appearance_sha256',
                'curb_geometry_sha256', 'camera_plan_sha256', 'ego_blueprint_sha256',
                'route_sha256', 'weather_sha256'):
        require(left['fixed_sources'].get(key) and left['fixed_sources'][key] == right['fixed_sources'].get(key), f'fixed source changed: {key}')
    for key in ('attended', 'property_kind', 'activity', 'target_region', 'exception'):
        if key == difference:
            require(left.get(key) != right.get(key), 'deliberate difference absent')
        else:
            require(left.get(key) == right.get(key), f'undeclared difference: {key}')
