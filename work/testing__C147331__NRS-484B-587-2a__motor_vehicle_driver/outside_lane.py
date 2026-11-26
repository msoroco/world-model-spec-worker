"""Source-gated C147331 lane/shoulder construction and original-frame measurement.

The adapter is supplied by the later Native operator. This module has no CARLA import.
Engineering lane geometry does not decide statutory authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    approach: str
    route_class: str
    vehicle_class: str = 'ordinary'
    sign_permits_shoulder: bool = False
    emergency_required: bool = False
    subsection3_authorized: bool = False


CASES = (
    Case('north_marked', 'north', 'traffic_lane'),
    Case('north_outside', 'north', 'outside_nonshoulder'),
    Case('south_marked', 'south', 'traffic_lane'),
    Case('south_outside', 'south', 'outside_nonshoulder'),
    Case('north_shoulder_unsigned', 'north', 'paved_shoulder'),
    Case('north_shoulder_signed_qualified', 'north', 'paved_shoulder', 'qualifying_484b210_4', True),
    Case('north_shoulder_signed_ordinary', 'north', 'paved_shoulder', 'ordinary', True),
    Case('north_outside_emergency', 'north', 'outside_nonshoulder', emergency_required=True),
    Case('north_shoulder_authorized', 'north', 'paved_shoulder', 'qualifying_484b587_3', True, False, True),
    Case('north_entrance', 'north', 'entrance_lane'),
    Case('north_exit', 'north', 'exit_lane'),
)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _point(point) -> bool:
    return isinstance(point, (tuple, list)) and len(point) == 2 and all(
        isinstance(x, (int, float)) and isfinite(x) for x in point)


def validate_site(site: Mapping) -> None:
    require(site.get('cell_id') == 'C147331' and site.get('layout') == 'one_way_multilane', 'wrong cell/layout')
    require(site.get('legal_controlled_access_source_sha256'), 'controlled-access designation source missing')
    require(site.get('public_highway_boundary_source_sha256'), 'highway boundary source missing')
    require(site.get('map_sha256') and site.get('lane_marking_source_sha256'), 'map/marking source missing')
    require(site.get('direction_of_travel') == 'one_way', 'one-way source missing')
    require(site.get('direction_source_sha256'), 'travel direction source missing')
    direction = site.get('approach_vector')
    require(_point(direction), 'approach vector missing')
    dx, dy = direction
    require(dx*dx + dy*dy > 0, 'approach vector zero')
    require(site.get('approach') in ('north', 'south'), 'approach designation missing')
    lanes = site.get('lanes', {})
    for key in ('traffic_left', 'traffic_right', 'entrance', 'exit', 'shoulder', 'outside'):
        lane = lanes.get(key, {})
        require(lane.get('source_sha256') and lane.get('id'), f'{key} source missing')
        require(len(lane.get('route', [])) >= 2 and all(_point(p) for p in lane['route']), f'{key} route invalid')
        require(lane.get('classification') == key, f'{key} classification mismatch')
        route = lane['route']
        progress = (route[-1][0]-route[0][0])*dx + (route[-1][1]-route[0][1])*dy
        require(progress > 0, f'{key} route opposes sourced approach')
    require(lanes['traffic_left']['id'] != lanes['traffic_right']['id'], 'two marked travel lanes missing')
    require(site.get('shoulder_paved_source_sha256'), 'paved shoulder source missing')
    require(site.get('sign_source_sha256'), 'sign inventory source missing')
    require(site.get('vehicle_class_source_sha256'), 'vehicle class source missing')
    require(site.get('emergency_record_source_sha256'), 'emergency record source missing')
    require(site.get('subsection3_authorization_source_sha256'), 'authorization source missing')


def route_key(case: Case) -> str:
    return {'traffic_lane': 'traffic_right', 'outside_nonshoulder': 'outside',
            'paved_shoulder': 'shoulder', 'entrance_lane': 'entrance',
            'exit_lane': 'exit'}[case.route_class]


def build_case(adapter, site: Mapping, case: Case) -> dict:
    validate_site(site)
    require(case in CASES, 'unknown exact case')
    require(site.get('approach') == case.approach, 'approach source differs from case')
    key = route_key(case)
    lane = site['lanes'][key]
    require(bool(site.get('sign_permits_shoulder')) == case.sign_permits_shoulder,
            'signed shoulder condition differs from case')
    require(bool(site.get('emergency_required')) == case.emergency_required,
            'emergency condition differs from case')
    require(bool(site.get('subsection3_authorized')) == case.subsection3_authorized,
            'authorization condition differs from case')
    require(site.get('vehicle_class') == case.vehicle_class, 'vehicle class differs from case')
    ego = adapter.spawn_vehicle(lane['route'][0], role='ego', vehicle_class=case.vehicle_class)
    require(ego is not None, 'ego spawn failed')
    try:
        adapter.set_route(ego, lane['route'], target_speed_mps=8.0)
        adapter.set_capture_metadata(ego, {'case': case.name, 'route_class': case.route_class,
                                           'map_sha256': site['map_sha256'],
                                           'lane_marking_source_sha256': site['lane_marking_source_sha256']})
        return {'ego': ego, 'owned': (ego,), 'route_id': lane['id'], 'case': case.name}
    except Exception:
        adapter.destroy(ego)
        raise


def measure_original(rows: list[Mapping], case: Case) -> dict:
    require(case in CASES, 'unknown exact case')
    require(len(rows) >= 2, 'original history too short')
    first = rows[0].get('original_frame')
    require(type(first) is int, 'original frame missing')
    fixed = ('case', 'ego_id', 'map_sha256', 'lane_marking_source_sha256',
             'legal_controlled_access_source_sha256', 'public_highway_boundary_source_sha256',
             'camera_plan_sha256', 'direction_source_sha256', 'vehicle_class', 'approach', 'sign_source_sha256',
             'emergency_record_source_sha256', 'subsection3_authorization_source_sha256')
    baseline = {key: rows[0].get(key) for key in fixed}
    require(all(baseline.values()), 'fixed original source missing')
    require(baseline['case'] == case.name and baseline['vehicle_class'] == case.vehicle_class
            and baseline['approach'] == case.approach, 'case/source join mismatch')
    samples = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first+i and row.get('source_sha256'), 'original frame/source discontinuity')
        require(all(row.get(key) == val for key, val in baseline.items()), 'fixed source changed')
        require(row.get('route_class') == case.route_class, 'route classification changed')
        require(row.get('sign_permits_shoulder') is case.sign_permits_shoulder, 'sign condition changed')
        require(row.get('emergency_required') is case.emergency_required, 'emergency condition changed')
        require(row.get('subsection3_authorized') is case.subsection3_authorized, 'authorization condition changed')
        for key in ('ego_lateral_m', 'ego_speed_mps', 'left_marking_lateral_m',
                    'right_marking_lateral_m', 'shoulder_outer_lateral_m'):
            require(isinstance(row.get(key), (int, float)) and isfinite(row[key]), f'{key} missing')
        samples.append({'original_frame': first+i, 'ego_lateral_m': row['ego_lateral_m'],
                        'ego_speed_mps': row['ego_speed_mps'],
                        'left_marking_lateral_m': row['left_marking_lateral_m'],
                        'right_marking_lateral_m': row['right_marking_lateral_m'],
                        'shoulder_outer_lateral_m': row['shoulder_outer_lateral_m']})
    return {'case': case.name, 'frame_count': len(rows), 'first_original_frame': first,
            'last_original_frame': first+len(rows)-1, 'fixed': baseline,
            'samples': samples, 'route_class': case.route_class, 'vehicle_class': case.vehicle_class,
            'approach': case.approach, 'sign_permits_shoulder': case.sign_permits_shoulder,
            'emergency_required': case.emergency_required,
            'subsection3_authorized': case.subsection3_authorized,
            'legal_judgment': None, 'physical_visibility_verified': False}


def audit_comparison(left: Mapping, right: Mapping, changed: set[str]) -> dict:
    require(left.get('frame_count') == right.get('frame_count') == 900, 'incomplete original recording')
    require(left.get('case') != right.get('case'), 'duplicate case')
    a, b = left.get('fixed', {}), right.get('fixed', {})
    for key in ('map_sha256', 'lane_marking_source_sha256', 'legal_controlled_access_source_sha256',
                'public_highway_boundary_source_sha256', 'camera_plan_sha256', 'direction_source_sha256'):
        require(a.get(key) and a.get(key) == b.get(key), f'fixed source changed: {key}')
    for key in ('vehicle_class', 'approach', 'route_class', 'sign_permits_shoulder',
                'emergency_required', 'subsection3_authorized'):
        if key in changed:
            require(left.get(key) != right.get(key), f'deliberate difference absent: {key}')
        else:
            require(left.get(key) == right.get(key), f'fixed condition changed: {key}')
    require(left.get('original_history_sha256') and right.get('original_history_sha256'), 'original source missing')
    return {'case_ids': [left['case'], right['case']], 'changed': sorted(changed), 'legal_judgment': None}
