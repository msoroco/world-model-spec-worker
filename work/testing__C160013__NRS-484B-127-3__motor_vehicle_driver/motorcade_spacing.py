"""Source-gated group spacing construction and original-frame measurements.

Requested geometry is an engineering target. This module makes no judgment about
whether the space is sufficient or an entry would be without danger.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    suffix: str
    group_kind: str
    gap_target_m: float
    towing: bool = False
    combination_entrant: bool = False


CASES = tuple(
    Case(f'{group}_none_{level}', group, gap)
    for group in ('caravan', 'motorcade')
    for level, gap in (('near', 18.0), ('middle', 60.0), ('far', 103.0))
) + tuple(
    Case(f'{group}_towing_middle', group, 60.0, towing=True)
    for group in ('caravan', 'motorcade')
) + tuple(
    Case(f'{group}_none_middle_combination_entrant', group, 60.0,
         combination_entrant=True)
    for group in ('caravan', 'motorcade')
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), label + ' must be a finite Native number')
    return float(value)


def validate_source_packet(packet, case):
    """Check reviewed route, legal assumptions, roles, assets and view survey."""
    require(packet.get('case_suffix') == case.suffix, 'exact case source mismatch')
    route = packet.get('route') or {}
    require(route.get('native_road_id') and route.get('directed_driving_lane_id'),
            'Native highway route identity required')
    require(number(route.get('surveyed_length_m'), 'route length') >= 620,
            'surveyed route too short for 30-second group and entrant episode')
    require(route.get('public_highway_review') and route.get('outside_business_district_review'),
            'external highway and district context required')
    membership = packet.get('membership') or {}
    require(membership.get('group_kind') == case.group_kind,
            'independent caravan or motorcade source required')
    require(membership.get('reviewer') and membership.get('coordination_source')
            and membership.get('ordered_roles') == ['front', 'ego', 'rear'],
            'reviewed ordered group membership required')
    require(membership.get('driver_relationships') and membership.get('group_purpose'),
            'group relationship cannot be inferred from common motion')
    assets = packet.get('assets') or {}
    for role in ('front', 'ego', 'rear', 'entrant'):
        vehicle = assets.get(role) or {}
        require(vehicle.get('blueprint_id') and vehicle.get('native_vehicle_class') == 'motor_vehicle',
                'Native qualifying motor vehicle source required: ' + role)
        require(number(vehicle.get('body_length_m'), role + ' body length') > 2,
                'body length must be positive: ' + role)
    require(bool(assets.get('group_towed_vehicle')) == case.towing,
            'group towing alternative mismatch')
    require(bool(assets.get('entrant_towed_vehicle')) == case.combination_entrant,
            'entrant combination alternative mismatch')
    views = packet.get('camera_survey') or []
    require([view.get('name') for view in views] ==
            ['overview', 'approach', 'reference_corner', 'driver_reference'],
            'four-camera source survey required')
    require(all(view.get('native_pose') and view.get('reviewer') for view in views),
            'reviewed Native camera poses required')
    return packet


def planned_spawn(packet, case):
    """Derive four spawn stations from surveyed Native body lengths and gaps."""
    validate_source_packet(packet, case)
    assets = packet['assets']
    lengths = {role: float(assets[role]['body_length_m'])
               for role in ('front', 'ego', 'rear', 'entrant')}
    if case.towing:
        lengths['ego'] += float(assets['group_towed_vehicle']['body_length_m'])
    if case.combination_entrant:
        lengths['entrant'] += float(assets['entrant_towed_vehicle']['body_length_m'])
    centre = 175.0
    ego = centre
    front = ego + 0.5 * (lengths['ego'] + lengths['front']) + case.gap_target_m
    rear = ego - 0.5 * (lengths['ego'] + lengths['rear']) - case.gap_target_m
    require(front + 9.1 * 30 < float(packet['route']['surveyed_length_m']) - 20 and rear > 20,
            'surveyed route cannot fit requested body gaps')
    entrant = ego - 12.0
    return {'front': front, 'ego': ego, 'rear': rear, 'entrant': entrant,
            'body_lengths_m': lengths, 'gap_target_m': case.gap_target_m,
            'entrant_lateral_source': packet['route'].get('entrant_adjacent_lane_id')}


def execute_case(adapter, packet, case):
    """Request concrete actors and 600 synchronized ticks from a Native adapter."""
    spawn = planned_spawn(packet, case)
    require(spawn['entrant_lateral_source'], 'Native entrant adjacent lane required')
    adapter.open_route(packet['route'])
    for role in ('front', 'ego', 'rear'):
        adapter.spawn_group_vehicle(role, packet['assets'][role], spawn[role],
                                    packet['route']['directed_driving_lane_id'])
    if case.towing:
        adapter.attach_towed_vehicle('ego', packet['assets']['group_towed_vehicle'])
    adapter.spawn_entrant(packet['assets']['entrant'], spawn['entrant'],
                          spawn['entrant_lateral_source'])
    if case.combination_entrant:
        adapter.attach_towed_vehicle('entrant', packet['assets']['entrant_towed_vehicle'])
    adapter.set_group_motion(9.1, case.gap_target_m)
    adapter.schedule_entrant_entry(start_s=14.0, end_s=20.0,
                                   target_gap_roles=('front', 'ego'))
    adapter.capture_original(case.suffix, 600, packet['camera_survey'])
    return spawn


def body_interval(body, role):
    vertices = body.get('route_station_vertices_m')
    require(isinstance(vertices, list) and len(vertices) == 8,
            'all eight Native body vertices required: ' + role)
    values = [number(v, role + ' route vertex') for v in vertices]
    return min(values), max(values)


def measure_original_frames(frames, case):
    """Measure body clear spaces and entry history from all original frames."""
    require(len(frames) == 600, 'all 600 original frames required')
    before = []
    after = []
    for index, frame in enumerate(frames):
        require(frame.get('frame') == index and
                abs(number(frame.get('time_s'), 'frame time') - index / 20.0) < 1e-6,
                'original frame/time join mismatch')
        bodies = frame.get('bodies') or {}
        require(set(bodies) >= {'front', 'ego', 'rear', 'entrant'},
                'all group and outsider bodies required')
        interval = {role: body_interval(bodies[role], role)
                    for role in ('front', 'ego', 'rear', 'entrant')}
        front_gap = interval['front'][0] - interval['ego'][1]
        rear_gap = interval['ego'][0] - interval['rear'][1]
        sample = {'time_s': index / 20.0, 'front_group_clear_gap_m': front_gap,
                  'rear_group_clear_gap_m': rear_gap,
                  'entrant_route_interval_m': interval['entrant'],
                  'entrant_lane_id': bodies['entrant'].get('native_lane_id'),
                  'collision_events': frame.get('collision_events', []),
                  'group_role_ids': frame.get('group_role_ids'),
                  'controls': frame.get('controls')}
        require(sample['group_role_ids'] and sample['controls'] is not None,
                'group identities and controls must be retained independently')
        (before if 8 <= sample['time_s'] < 14 else after).append(sample)
    require(len(before) == 120, 'steady source window incomplete')
    return {
        'steady_front_mean_m': sum(x['front_group_clear_gap_m'] for x in before) / 120,
        'steady_rear_mean_m': sum(x['rear_group_clear_gap_m'] for x in before) / 120,
        'steady_source': before,
        'later_source': after,
        'requested_gap_m': case.gap_target_m,
        'legal_sufficiency': None,
        'without_danger': None,
    }
