"""Source-gated sidewalk-elevator parking construction and saved-frame measurements.

Distances are geometric observations. They are not a legal measurement convention
or a conclusion that the statutory object and exception are established.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

CELL = 'C150153'
LAW = 'LVMC-11-52-130-A5'
FIVE_FEET_M = 1.524


@dataclass(frozen=True)
class Case:
    id: str
    region: str
    activity: str
    gap_m: float
    exception: str = 'none'


CASES = (
    Case('front_park', 'front', 'park', 0.0),
    Case('front_stop', 'front', 'stop', 0.0),
    Case('front_stand', 'front', 'stand', 0.0),
    Case('west_inside', 'west', 'park', 1.374),
    Case('west_at', 'west', 'park', 1.524),
    Case('west_outside', 'west', 'park', 1.674),
    Case('east_inside', 'east', 'park', 1.374),
    Case('east_at', 'east', 'park', 1.524),
    Case('east_outside', 'east', 'park', 1.674),
    Case('front_traffic_exception', 'front', 'stop', 0.0, 'lawful_traffic_conflict'),
    Case('front_police_exception', 'front', 'stop', 0.0, 'police_direction'),
    Case('front_device_exception', 'front', 'stop', 0.0, 'traffic_device_direction'),
)


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _number(value, name: str) -> float:
    need(type(value) in (int, float) and isfinite(value), f'{name} invalid')
    return float(value)


def validate_site(site: Mapping) -> None:
    need(site.get('cell_id') == CELL and site.get('layout') == 'one_way_road', 'wrong cell or layout')
    for key in ('map_sha256', 'municipal_jurisdiction_sha256', 'sidewalk_sha256',
                'fixture_identity_sha256', 'fixture_geometry_sha256', 'curb_sha256',
                'one_way_direction_sha256', 'fixture_blueprint_sha256'):
        need(bool(site.get(key)), f'{key} source missing')
    need(site.get('fixture_kind') == 'sidewalk_elevator', 'fixture kind unsupported')
    need(site.get('fixture_physical_support') in ('map_object', 'spawned_prop'),
         'fixture physical support missing')
    fixture = site.get('fixture', {})
    west = _number(fixture.get('west_x_m'), 'fixture west')
    east = _number(fixture.get('east_x_m'), 'fixture east')
    curb = _number(fixture.get('curb_y_m'), 'fixture curb')
    need(east > west and _number(fixture.get('sidewalk_depth_m'), 'sidewalk depth') > 0,
         'fixture geometry invalid')
    need(isinstance(site.get('approach_waypoints'), list) and len(site['approach_waypoints']) >= 2,
         'approach route source missing')
    need(all(len(point) == 2 and all(type(v) in (int, float) and isfinite(v) for v in point)
             for point in site['approach_waypoints']), 'approach route invalid')
    need(site['approach_waypoints'][0][0] < site['approach_waypoints'][-1][0],
         'one-way approach reversed')
    need(site.get('ego_blueprint_sha256') and site.get('camera_plan_sha256'),
         'vehicle or camera source missing')
    need(curb == site.get('curb_y_m'), 'curb source does not match fixture')


def target_body_interval(site: Mapping, case: Case, body_length_m: float) -> tuple[float, float]:
    """Return commanded body interval along the curb, never a measured outcome."""
    need(case in CASES, 'unknown case')
    length = _number(body_length_m, 'body length')
    need(length > 0, 'body length invalid')
    fixture = site['fixture']
    west, east = fixture['west_x_m'], fixture['east_x_m']
    if case.region == 'west':
        return west - case.gap_m - length, west - case.gap_m
    if case.region == 'east':
        return east + case.gap_m, east + case.gap_m + length
    center = (west + east) / 2
    return center - length / 2, center + length / 2


def build_case(adapter, site: Mapping, case: Case, body_length_m: float):
    """Create/read back the actual fixture, ego and direction source with cleanup."""
    validate_site(site)
    need(case in CASES, 'unknown case')
    interval = target_body_interval(site, case, body_length_m)
    owned = []
    try:
        if site['fixture_physical_support'] == 'spawned_prop':
            fixture = adapter.spawn_fixture(site['fixture'], blueprint_sha256=site['fixture_blueprint_sha256'])
            need(fixture is not None, 'sidewalk elevator fixture spawn failed')
            owned.append(fixture)
        else:
            fixture = adapter.lookup_fixture(site['fixture_identity_sha256'])
            need(fixture is not None, 'mapped sidewalk elevator missing')
        readback = adapter.read_fixture(fixture)
        need(readback.get('identity_sha256') == site['fixture_identity_sha256'], 'fixture identity readback mismatch')
        need(readback.get('geometry_sha256') == site['fixture_geometry_sha256'], 'fixture geometry readback mismatch')
        need(readback.get('physically_present') is True, 'fixture physical presence not read back')
        ego = adapter.spawn_vehicle(site['approach_waypoints'][0], blueprint_sha256=site['ego_blueprint_sha256'])
        need(ego is not None, 'ego spawn failed')
        owned.append(ego)
        adapter.set_route(ego, site['approach_waypoints'], one_way=True)
        adapter.set_curb_target(ego, interval, site['curb_y_m'], activity=case.activity)
        if case.exception != 'none':
            source_key = {'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
                          'police_direction': 'police_direction_source_sha256',
                          'traffic_device_direction': 'traffic_device_source_sha256'}[case.exception]
            need(site.get(source_key), f'{case.exception} source missing')
            adapter.set_exception_source(ego, case.exception, site[source_key])
        return {'case_id': case.id, 'ego': ego, 'fixture': fixture,
                'target_body_interval_m': interval, 'owned': tuple(owned)}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def _gap(body_west: float, body_east: float, fixture_west: float, fixture_east: float):
    if body_east < fixture_west:
        return 'west', fixture_west - body_east
    if body_west > fixture_east:
        return 'east', body_west - fixture_east
    return 'front_overlap', 0.0


def measure_original_history(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    """Measure observed body edges and activity from contiguous original frames."""
    validate_site(site)
    need(case in CASES and len(rows) >= 2, 'case or original history missing')
    fixed = {key: rows[0].get(key) for key in ('ego_id', 'fixture_id', 'map_sha256',
                                             'fixture_identity_sha256', 'fixture_geometry_sha256',
                                             'camera_plan_sha256', 'jurisdiction_sha256')}
    need(all(fixed.values()), 'original fixed sources missing')
    need(fixed['map_sha256'] == site['map_sha256'] and
         fixed['fixture_identity_sha256'] == site['fixture_identity_sha256'] and
         fixed['fixture_geometry_sha256'] == site['fixture_geometry_sha256'] and
         fixed['camera_plan_sha256'] == site['camera_plan_sha256'] and
         fixed['jurisdiction_sha256'] == site['municipal_jurisdiction_sha256'],
         'original source differs from site')
    first = rows[0].get('original_frame')
    need(type(first) is int, 'original frame identity missing')
    measured = []
    for i, row in enumerate(rows):
        need(row.get('case_id') == case.id and row.get('original_frame') == first + i,
             'case or original frame join mismatch')
        need(all(row.get(key) == value for key, value in fixed.items()), 'fixed source changed')
        need(bool(row.get('source_sha256')) and bool(row.get('frame_map_sha256')),
             'original frame source missing')
        west = _number(row.get('body_west_x_m'), 'body west')
        east = _number(row.get('body_east_x_m'), 'body east')
        need(east > west, 'body footprint invalid')
        curb_gap = _number(row.get('body_curb_gap_m'), 'body curb gap')
        need(curb_gap >= 0, 'body curb gap invalid')
        speed = _number(row.get('ego_speed_mps'), 'ego speed')
        need(speed >= 0, 'ego speed invalid')
        need(row.get('activity_observation') in ('moving', 'stopped', 'standing', 'parked'),
             'activity observation missing')
        need(row.get('exception_source_sha256') if case.exception != 'none' else
             row.get('exception_source_sha256') is None, 'exception source missing or changed')
        region, gap = _gap(west, east, site['fixture']['west_x_m'], site['fixture']['east_x_m'])
        measured.append({'original_frame': first + i, 'region': region,
                         'side_gap_m': gap, 'curb_gap_m': curb_gap, 'speed_mps': speed,
                         'activity_observation': row['activity_observation']})
    return {'case_id': case.id, 'first_original_frame': first,
            'last_original_frame': first + len(rows) - 1, 'frame_count': len(rows),
            'min_side_gap_m': min(m['side_gap_m'] for m in measured),
            'front_overlap_frames': sum(m['region'] == 'front_overlap' for m in measured),
            'observed_regions': sorted({m['region'] for m in measured}),
            'observed_activities': sorted({m['activity_observation'] for m in measured}),
            'original_measurements': measured, 'source_identity': fixed,
            'five_feet_m_reference': FIVE_FEET_M, 'legal_judgment': None,
            'physical_visibility_verified': False}


def audit_comparison(left: Mapping, right: Mapping, deliberate_difference: str) -> None:
    """Independent comparison guard over source-bound original measurements."""
    need(left.get('case_id') != right.get('case_id'), 'same case compared')
    for side in (left, right):
        need(side.get('frame_count') == 900 and side.get('original_history_sha256') and
             side.get('source_identity') and side.get('camera_plan_sha256'),
             'comparison source or duration missing')
    comparable_sources = ('map_sha256', 'fixture_identity_sha256', 'fixture_geometry_sha256',
                          'camera_plan_sha256', 'jurisdiction_sha256')
    need(all(left['source_identity'].get(k) and
             left['source_identity'].get(k) == right['source_identity'].get(k)
             for k in comparable_sources), 'fixture or map changed')
    need(left['camera_plan_sha256'] == right['camera_plan_sha256'], 'camera plan changed')
    fixed = ('ego_blueprint_sha256', 'weather_sha256', 'route_sha256', 'curb_gap_target_m')
    for key in fixed:
        if key != deliberate_difference:
            need(left.get(key) and left.get(key) == right.get(key), f'fixed condition changed: {key}')
    need(deliberate_difference in left and deliberate_difference in right and
         left[deliberate_difference] != right[deliberate_difference],
         'deliberate difference absent')
