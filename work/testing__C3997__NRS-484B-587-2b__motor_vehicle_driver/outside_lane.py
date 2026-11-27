"""Source-gated solid-white separator construction and original-frame measurement.

Geometry and source records remain observations for review, not a legal verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    approach: str
    origin: str
    destination: str
    emergency_required: bool = False
    subsection3_shoulder_authorized: bool = False
    vehicle_class: str = 'ordinary_motor_vehicle'


CASES = (
    Case('north_traffic_stay', 'north', 'traffic', 'traffic'),
    Case('north_traffic_to_entrance', 'north', 'traffic', 'entrance'),
    Case('north_entrance_to_traffic', 'north', 'entrance', 'traffic'),
    Case('north_traffic_to_exit', 'north', 'traffic', 'exit'),
    Case('north_exit_to_traffic', 'north', 'exit', 'traffic'),
    Case('south_traffic_stay', 'south', 'traffic', 'traffic'),
    Case('south_traffic_to_entrance', 'south', 'traffic', 'entrance'),
    Case('south_traffic_to_exit', 'south', 'traffic', 'exit'),
    Case('north_traffic_to_exit_emergency', 'north', 'traffic', 'exit', True),
    Case('north_traffic_to_exit_shoulder_authorized', 'north', 'traffic', 'exit',
         False, True, 'qualifying_484b587_3'),
)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def point(value) -> bool:
    return isinstance(value, (tuple, list)) and len(value) == 2 and all(
        type(x) in (int, float) and isfinite(x) for x in value)


def signed_distance(xy, line):
    anchor, normal = line['anchor_xy'], line['normal_xy']
    return (xy[0] - anchor[0]) * normal[0] + (xy[1] - anchor[1]) * normal[1]


def segment_fraction(xy, line):
    start, end = line['start_xy'], line['end_xy']
    dx, dy = end[0] - start[0], end[1] - start[1]
    return ((xy[0] - start[0]) * dx + (xy[1] - start[1]) * dy) / (dx * dx + dy * dy)


def crosses_separator(route, line) -> bool:
    distances = [signed_distance(p, line) for p in route]
    return (distances[0] < -0.5 and distances[-1] > 0.5 or
            distances[0] > 0.5 and distances[-1] < -0.5) and any(
                a * b <= 0 and 0 <= segment_fraction((
                    p[0] + (q[0] - p[0]) * (abs(a) / (abs(a) + abs(b))),
                    p[1] + (q[1] - p[1]) * (abs(a) / (abs(a) + abs(b)))), line) <= 1
                for p, q, a, b in zip(route, route[1:], distances, distances[1:])
                if abs(a) + abs(b) > 0)


def validate_site(site: Mapping) -> None:
    require(site.get('cell_id') == 'C3997' and site.get('layout') == 'adjacent_lanes',
            'wrong cell/layout')
    for key in ('legal_controlled_access_source_sha256',
                'public_highway_boundary_source_sha256', 'map_sha256',
                'lane_marking_source_sha256', 'lane_function_source_sha256',
                'direction_source_sha256', 'vehicle_class_source_sha256',
                'paved_shoulder_source_sha256',
                'lawful_shoulder_sign_source_sha256',
                'emergency_record_source_sha256',
                'subsection3_authorization_source_sha256',
                'native_spawn_source_sha256', 'camera_plan_sha256'):
        require(isinstance(site.get(key), str) and len(site[key]) >= 8,
                key + ' source missing')
    require(site.get('lane_change_control') == 'solid_white_line',
            'fixed cell control differs')
    require(site.get('approach') in ('north', 'south'), 'approach source missing')
    direction = site.get('approach_vector')
    require(point(direction) and hypot(*direction) > 0.5,
            'approach vector missing')
    routes = site.get('routes', {})
    for case in CASES:
        if case.approach != site['approach']:
            continue
        route = routes.get(case.name)
        require(isinstance(route, dict) and route.get('source_sha256') in
                (site['map_sha256'], site['lane_marking_source_sha256']),
                'sourced exact route missing: ' + case.name)
        points = route.get('points')
        require(isinstance(points, list) and len(points) >= 3 and all(map(point, points)),
                'exact route points missing: ' + case.name)
        require(route.get('origin') == case.origin and
                route.get('destination') == case.destination,
                'route lane function differs: ' + case.name)
        progress = (points[-1][0] - points[0][0]) * direction[0] + (
            points[-1][1] - points[0][1]) * direction[1]
        require(progress > 5, 'route opposes sourced approach: ' + case.name)
        line = route.get('separator')
        require(isinstance(line, dict) and point(line.get('anchor_xy')) and
                point(line.get('normal_xy')) and
                point(line.get('start_xy')) and point(line.get('end_xy')) and
                hypot(line['end_xy'][0] - line['start_xy'][0],
                      line['end_xy'][1] - line['start_xy'][1]) > 10 and
                0.9 <= hypot(*line['normal_xy']) <= 1.1,
                'separator geometry missing: ' + case.name)
        require(abs(signed_distance(line['start_xy'], line)) < 1e-6 and
                abs(signed_distance(line['end_xy'], line)) < 1e-6,
                'separator endpoints leave sourced line: ' + case.name)
        adjacent = route.get('adjacent_lane') if case.origin == case.destination else (
            case.destination if case.origin == 'traffic' else case.origin)
        separated = sorted(('traffic', adjacent))
        require(adjacent in ('entrance', 'exit'),
                'adjacent lane function missing: ' + case.name)
        require(line.get('source_sha256') == site['lane_marking_source_sha256'] and
                line.get('kind') == 'solid_white' and
                line.get('separates') == separated,
                'solid-white separator source/function differs: ' + case.name)
        distances = [signed_distance(p, line) for p in points]
        if case.origin == case.destination:
            require(all(d < -0.5 for d in distances) or
                    all(d > 0.5 for d in distances),
                    'stay route crosses separator: ' + case.name)
        else:
            require(crosses_separator(points, line),
                    'crossing route misses separator: ' + case.name)


def build_case(adapter, site: Mapping, case: Case) -> dict:
    require(case in CASES, 'unknown exact case')
    validate_site(site)
    require(site.get('approach') == case.approach,
            'approach source differs from case')
    require(bool(site.get('emergency_required')) == case.emergency_required,
            'emergency condition differs from case')
    require(bool(site.get('subsection3_shoulder_authorized')) ==
            case.subsection3_shoulder_authorized,
            'subsection 3 condition differs from case')
    if case.subsection3_shoulder_authorized:
        require(site.get('shoulder_paved') is True and
                site.get('lawful_sign_permits_shoulder') is True,
                'subsection 3 paving or lawful sign source missing')
    require(site.get('vehicle_class') == case.vehicle_class,
            'vehicle class differs from case')
    route = site['routes'][case.name]
    ego = adapter.spawn_vehicle(route['points'][0], role='ego',
                                vehicle_class=case.vehicle_class)
    require(ego is not None, 'ego spawn failed')
    try:
        adapter.set_route(ego, route['points'], target_speed_mps=8.0)
        adapter.set_capture_metadata(ego, {
            'case': case.name, 'route_id': route['id'],
            'origin': case.origin, 'destination': case.destination,
            'lane_marking_source_sha256': site['lane_marking_source_sha256']})
        return {'ego': ego, 'owned': (ego,), 'route_id': route['id'],
                'case': case.name}
    except Exception:
        adapter.destroy(ego)
        raise


def measure_original(rows: list[Mapping], case: Case) -> dict:
    require(case in CASES, 'unknown exact case')
    require(len(rows) >= 2, 'original history too short')
    first = rows[0].get('original_frame')
    require(type(first) is int, 'original frame missing')
    keys = ('case', 'ego_id', 'map_sha256', 'lane_marking_source_sha256',
            'lane_function_source_sha256',
            'legal_controlled_access_source_sha256',
            'public_highway_boundary_source_sha256', 'direction_source_sha256',
            'camera_plan_sha256', 'vehicle_class_source_sha256', 'vehicle_class',
            'paved_shoulder_source_sha256',
            'lawful_shoulder_sign_source_sha256',
            'emergency_record_source_sha256',
            'subsection3_authorization_source_sha256', 'route_id',
            'approach', 'origin', 'destination', 'separator_kind',
            'separator_source_sha256')
    fixed = {key: rows[0].get(key) for key in keys}
    require(all(fixed.values()), 'fixed original source missing')
    require(fixed['case'] == case.name and fixed['approach'] == case.approach and
            fixed['origin'] == case.origin and
            fixed['destination'] == case.destination and
            fixed['vehicle_class'] == case.vehicle_class and
            fixed['separator_kind'] == 'solid_white',
            'case/source join mismatch')
    samples = []
    for index, row in enumerate(rows):
        require(row.get('original_frame') == first + index and
                row.get('source_sha256'), 'original frame/source discontinuity')
        require(all(row.get(key) == value for key, value in fixed.items()),
                'fixed original source changed')
        require(row.get('emergency_required') is case.emergency_required and
                row.get('subsection3_shoulder_authorized') is
                case.subsection3_shoulder_authorized,
                'exception context changed')
        require(type(row.get('shoulder_paved')) is bool and
                type(row.get('lawful_sign_permits_shoulder')) is bool,
                'shoulder context missing')
        require(row['shoulder_paved'] is rows[0]['shoulder_paved'] and
                row['lawful_sign_permits_shoulder'] is
                rows[0]['lawful_sign_permits_shoulder'],
                'shoulder context changed')
        if case.subsection3_shoulder_authorized:
            require(row['shoulder_paved'] and
                    row['lawful_sign_permits_shoulder'],
                    'subsection 3 paving or lawful sign source missing')
        for key in ('ego_speed_mps', 'center_signed_m',
                    'body_min_signed_m', 'body_max_signed_m',
                    'center_segment_fraction', 'body_min_segment_fraction',
                    'body_max_segment_fraction'):
            require(type(row.get(key)) in (int, float) and isfinite(row[key]),
                    key + ' missing')
        require(row['body_min_signed_m'] <= row['center_signed_m'] <=
                row['body_max_signed_m'],
                'original body footprint does not contain center')
        require(row['body_min_segment_fraction'] <= row['center_segment_fraction'] <=
                row['body_max_segment_fraction'],
                'original body longitudinal footprint does not contain center')
        samples.append({key: row[key] for key in ('original_frame',
                       'ego_speed_mps', 'center_signed_m',
                       'body_min_signed_m', 'body_max_signed_m',
                       'center_segment_fraction', 'body_min_segment_fraction',
                       'body_max_segment_fraction')})
    signed = [s['center_signed_m'] for s in samples]
    center_crossing = (min(signed) < 0 < max(signed) and any(
        a['center_signed_m'] * b['center_signed_m'] <= 0 and
        a['center_signed_m'] != b['center_signed_m'] and
        0 <= (a['center_segment_fraction'] +
              b['center_segment_fraction']) / 2 <= 1
        for a, b in zip(samples, samples[1:])))
    body_touch = any(s['body_min_signed_m'] <= 0 <= s['body_max_signed_m'] and
                     s['body_min_segment_fraction'] <= 1 and
                     s['body_max_segment_fraction'] >= 0
                     for s in samples)
    return {'case': case.name, 'frame_count': len(rows),
            'first_original_frame': first,
            'last_original_frame': first + len(rows) - 1, 'fixed': fixed,
            'samples': samples, 'center_crossing_observed': center_crossing,
            'body_line_contact_observed': body_touch,
            'emergency_required': case.emergency_required,
            'vehicle_class': case.vehicle_class,
            'subsection3_shoulder_authorized':
                case.subsection3_shoulder_authorized,
            'shoulder_paved': rows[0]['shoulder_paved'],
            'lawful_sign_permits_shoulder':
                rows[0]['lawful_sign_permits_shoulder'],
            'legal_judgment': None, 'physical_visibility_verified': False}


def audit_comparison(left: Mapping, right: Mapping,
                     changed: set[str]) -> dict:
    require(left.get('frame_count') == right.get('frame_count') == 900,
            'incomplete original recording')
    require(left.get('case') != right.get('case'), 'duplicate case')
    a, b = left.get('fixed', {}), right.get('fixed', {})
    for key in ('map_sha256', 'lane_marking_source_sha256',
                'lane_function_source_sha256',
                'legal_controlled_access_source_sha256',
                'public_highway_boundary_source_sha256',
                'direction_source_sha256', 'camera_plan_sha256'):
        require(a.get(key) and a.get(key) == b.get(key),
                'fixed source changed: ' + key)
    for key in ('approach', 'origin', 'destination', 'vehicle_class',
                'emergency_required', 'subsection3_shoulder_authorized',
                'shoulder_paved', 'lawful_sign_permits_shoulder'):
        av = a.get(key) if key in a else left.get(key)
        bv = b.get(key) if key in b else right.get(key)
        if key in changed:
            require(av != bv, 'deliberate difference absent: ' + key)
        else:
            require(av == bv, 'fixed condition changed: ' + key)
    require(left.get('original_history_sha256') and
            right.get('original_history_sha256'), 'original source missing')
    return {'case_ids': [left['case'], right['case']],
            'changed': sorted(changed), 'legal_judgment': None}
