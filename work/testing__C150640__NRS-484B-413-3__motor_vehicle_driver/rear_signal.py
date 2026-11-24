"""Source-gated rear-recipient signaling probes for NRS 484B.413(3).

Event and signal timing are measured; appropriateness, immediacy and legal
necessity are never inferred from engineering distance or deceleration.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    maneuver: str
    signal_policy: str
    rear_driver: bool = True


CASES = (
    Case('stop_signal_before', 'stop', 'before'),
    Case('stop_signal_after', 'stop', 'after'),
    Case('decrease_signal_before', 'sudden_decrease', 'before'),
    Case('decrease_signal_after', 'sudden_decrease', 'after'),
    Case('stop_no_rear_driver', 'stop', 'before', False),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_number(value):
    return type(value) in (int, float) and isfinite(value)


def validate_scene(scene: Mapping):
    require(scene.get('cell_id') == 'C150640' and scene.get('actor') == 'motor_vehicle_driver',
            'wrong exact cell or actor')
    for field in ('jurisdiction', 'one_way_route', 'stop_footprint', 'ego_vehicle',
                  'ego_driver_control', 'signal_device', 'rear_visibility',
                  'conflict_context', 'official_direction_context'):
        require(scene.get(field + '_source_sha256'), 'original scene source missing: ' + field)
    route = scene.get('route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and
                all(finite_number(x) for x in p) for p in route), 'one-way route missing')
    footprint = scene.get('stop_footprint_xy')
    require(isinstance(footprint, list) and len(footprint) >= 3 and
            all(isinstance(p, list) and len(p) == 2 and
                all(finite_number(x) for x in p) for p in footprint),
            'stopping footprint missing')
    rear = scene.get('rear_vehicle')
    require(isinstance(rear, dict), 'rear vehicle declaration missing')
    for field in ('vehicle', 'driver', 'position', 'motion'):
        require(rear.get(field + '_source_sha256'), 'rear source missing: ' + field)
    require(rear.get('driver_present') in (True, False), 'rear driver state missing')
    require(finite_number(rear.get('longitudinal_gap_m')) and
            rear['longitudinal_gap_m'] > 0 and
            finite_number(rear.get('lateral_offset_m')),
            'rear longitudinal/lateral relation missing')
    return {'rear_driver_present': rear['driver_present'],
            'longitudinal_gap_m': rear['longitudinal_gap_m'],
            'lateral_offset_m': rear['lateral_offset_m'],
            'immediately_to_rear_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    relation = validate_scene(scene)
    require(case in CASES, 'unknown exact rear signal case')
    require(relation['rear_driver_present'] == case.rear_driver,
            'case rear driver condition differs from scene')
    owned = []
    try:
        ego = adapter.spawn_vehicle(scene['route_xy'][0], 'ego')
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        rear = adapter.spawn_vehicle(scene['rear_vehicle']['spawn_xy'], 'rear')
        require(rear is not None, 'rear vehicle spawn failed')
        owned.append(rear)
        adapter.set_route_and_stop(ego, scene['route_xy'], scene['stop_footprint_xy'],
                                   maneuver=case.maneuver)
        adapter.set_rear_driver(rear, present=case.rear_driver)
        adapter.set_signal_policy(ego, case.signal_policy)
        return {'case_id': case.case_id, 'owned': tuple(owned),
                'signal_policy': case.signal_policy, 'maneuver': case.maneuver,
                'legal_judgment': None}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    relation = validate_scene(scene)
    require(case in CASES and len(rows) == 900, 'exact 900-frame case missing')
    require(relation['rear_driver_present'] == case.rear_driver,
            'rear-driver condition mismatch')
    first = rows[0].get('original_frame')
    require(type(first) is int, 'original frame identity missing')
    ego_id = rear_id = None
    signals = []
    speeds = []
    events = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                finite_number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for name in ('source_sha256', 'ego_motion_source_sha256',
                     'rear_motion_source_sha256', 'signal_source_sha256',
                     'rear_visibility_source_sha256', 'context_source_sha256'):
            require(row.get(name), 'original source missing: ' + name)
        require(row.get('route_source_sha256') == scene['one_way_route_source_sha256'],
                'original route changed')
        require(row.get('ego_driver_in_control') is True and
                row.get('rear_driver_present') is case.rear_driver,
                'driver state changed')
        require(row.get('ego_id') and row.get('rear_id'), 'participant identity missing')
        ego_id = ego_id or row['ego_id']
        rear_id = rear_id or row['rear_id']
        require(row['ego_id'] == ego_id and row['rear_id'] == rear_id and ego_id != rear_id,
                'participant identity changed')
        for name in ('rear_longitudinal_gap_m', 'rear_lateral_offset_m',
                     'ego_speed_mps', 'rear_speed_mps'):
            require(finite_number(row.get(name)), 'original numeric stream missing: ' + name)
        require(row['rear_longitudinal_gap_m'] > 0, 'rear participant not rearward')
        require(type(row.get('signal_displayed')) is bool and
                type(row.get('signal_visible_from_rear')) is bool,
                'original signal/visibility missing')
        require(row.get('event_marker') in (None, 'stop', 'sudden_decrease'),
                'unsupported event marker')
        if row['signal_displayed']:
            signals.append(i)
        if row['event_marker'] == case.maneuver:
            events.append(i)
        speeds.append(row['ego_speed_mps'])
    require(len(events) == 1, 'one original maneuver onset required')
    event = events[0]
    require(bool(signals), 'actual displayed signal absent')
    onset = min(signals)
    require((onset < event) == (case.signal_policy == 'before'),
            'signal onset does not match controlled order')
    require(event > 0, 'event starts before motion history')
    if case.maneuver == 'stop':
        require(max(speeds[-20:]) <= .1, 'original stop absent')
    else:
        require(speeds[event] < speeds[event - 1], 'original speed decrease absent')
    return {'case_id': case.case_id, 'frame_count': 900,
            'signal_onset_frame': first + onset, 'event_onset_frame': first + event,
            'signal_precedes_event': onset < event,
            'signal_visible_from_rear_at_onset': rows[onset]['signal_visible_from_rear'],
            'rear_driver_present': case.rear_driver,
            'rear_gap_at_event_m': rows[event]['rear_longitudinal_gap_m'],
            'rear_lateral_offset_at_event_m': rows[event]['rear_lateral_offset_m'],
            'immediately_to_rear_judgment': None, 'signal_appropriateness_judgment': None,
            'conflict_and_official_direction_judgment': None, 'legal_judgment': None}
