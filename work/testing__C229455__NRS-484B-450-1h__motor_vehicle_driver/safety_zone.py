"""Source-bound safety-zone parking geometry and exact NRS 484B.450(1)(h) probes.

Distances are physical observations in metres. This module makes no legal finding.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

FOOT_M = 0.3048
THIRTY_FT_M = 30 * FOOT_M


@dataclass(frozen=True)
class Case:
    case_id: str
    placement: str
    end: str
    offset_m: float
    activity: str
    exception: str


CASES = (
    Case('between_park', 'between', 'west', 0.0, 'park', 'none'),
    Case('outside_corridor_park', 'outside', 'west', 0.0, 'park', 'none'),
    Case('west_end_below_30ft', 'end_band', 'west', THIRTY_FT_M - .1, 'park', 'none'),
    Case('west_end_at_30ft', 'end_band', 'west', THIRTY_FT_M, 'park', 'none'),
    Case('west_end_above_30ft', 'end_band', 'west', THIRTY_FT_M + .1, 'park', 'none'),
    Case('east_end_below_30ft', 'end_band', 'east', THIRTY_FT_M - .1, 'park', 'none'),
    Case('between_stop', 'between', 'west', 0.0, 'stop', 'none'),
    Case('between_stand', 'between', 'west', 0.0, 'stand', 'none'),
    Case('between_stop_conflict', 'between', 'west', 0.0, 'stop', 'conflict_avoidance'),
    Case('between_park_law', 'between', 'west', 0.0, 'park', 'law'),
    Case('between_stand_officer', 'between', 'west', 0.0, 'stand', 'officer_direction'),
    Case('between_park_device', 'between', 'west', 0.0, 'park', 'official_device'),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def point(value):
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(number(v) for v in value)


def rectangle(value):
    return (isinstance(value, (list, tuple)) and len(value) == 4 and
            all(number(v) for v in value) and value[0] < value[2] and value[1] < value[3])


def body_center(body):
    require(rectangle(body), 'original vehicle body rectangle missing')
    return [(body[0] + body[2]) / 2, (body[1] + body[3]) / 2]


def signed_end_station(point_xy, west, east, end):
    """Signed longitudinal distance outward from a selected zone end."""
    require(point(point_xy) and point(west) and point(east) and west[0] < east[0],
            'zone end and curb reference geometry missing')
    return west[0] - point_xy[0] if end == 'west' else point_xy[0] - east[0]


def between_zone_curb(body, zone, curb_y):
    """Body footprint lies entirely in the bounded longitudinal corridor."""
    require(rectangle(body) and rectangle(zone) and number(curb_y),
            'body, zone or curb geometry missing')
    return (body[0] >= zone[0] and body[2] <= zone[2] and
            body[1] >= zone[3] and body[3] <= curb_y)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact safety-zone case')
    require(scene.get('cell_id') == 'C229455' and scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('driver_present') is True and scene.get('motor_vehicle') is True,
            'qualifying driver or motor vehicle missing')
    require(scene.get('highway_public_access') is True and
            scene.get('safety_zone_designated_pedestrian_exclusive') is True,
            'highway or official pedestrian-exclusive designation missing')
    require(scene.get('safety_zone_set_apart_visible') is True and
            scene.get('safety_zone_marking_or_sign_source_sha256'),
            'safety-zone marking, signs or visibility source missing')
    require(scene.get('placement') == case.placement and
            scene.get('end') == case.end and
            scene.get('activity') == case.activity and
            scene.get('exception') == case.exception,
            'exact case variables changed')
    zone, target = scene.get('zone_rect_m'), scene.get('target_body_rect_m')
    require(rectangle(zone) and rectangle(target), 'zone/body geometry missing')
    require(number(scene.get('adjacent_curb_y_m')) and
            scene['adjacent_curb_y_m'] > zone[3], 'adjacent curb missing')
    west, east = scene.get('west_end_curb_point_m'), scene.get('east_end_curb_point_m')
    require(point(west) and point(east) and west[0] == zone[0] and east[0] == zone[2] and
            west[1] == east[1] == scene['adjacent_curb_y_m'],
            'opposite zone-end curb reference missing')
    require(point(scene.get('vehicle_target_xy')) and
            point(scene.get('vehicle_start_xy')), 'vehicle route endpoints missing')
    require(point(scene.get('traffic_start_xy')) and point(scene.get('traffic_target_xy')),
            'traffic route endpoints missing')
    for name in ('vehicle_route_xy', 'traffic_route_xy'):
        route = scene.get(name)
        require(isinstance(route, list) and len(route) >= 2 and all(point(p) for p in route),
                'original route missing: ' + name)
    if case.placement == 'between':
        require(between_zone_curb(target, zone, scene['adjacent_curb_y_m']),
                'between-zone-and-curb body placement not constructed')
    elif case.placement == 'outside':
        require(not between_zone_curb(target, zone, scene['adjacent_curb_y_m']) and
                target[0] >= zone[0] and target[2] <= zone[2],
                'outside corridor contrast not constructed')
    else:
        reference = west if case.end == 'west' else east
        distance = signed_end_station(body_center(target), west, east, case.end)
        require(distance > 0 and abs(distance - case.offset_m) <= .001,
                'opposite-end parking station does not match exact case')
        require(abs(scene['vehicle_target_xy'][0] - body_center(target)[0]) <= .001,
                'target differs from body centre')
    for name in ('map', 'highway', 'zone', 'curb', 'designation', 'vehicle', 'driver',
                 'route', 'traffic', 'activity', 'exception'):
        require(scene.get(name + '_source_sha256'), 'original source missing: ' + name)
    if case.exception == 'conflict_avoidance':
        require(scene.get('conflicting_traffic_id'), 'conflict actor missing')
    if case.exception in ('law', 'officer_direction', 'official_device'):
        require(scene.get('authority_record_id'), 'authority record missing')
    return {'case_id': case.case_id, 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        adapter.place_zone(scene['zone_rect_m'], scene['adjacent_curb_y_m'])
        ego = adapter.spawn_motor_vehicle(scene['vehicle_start_xy'])
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        traffic = adapter.spawn_traffic(scene['traffic_start_xy'])
        require(traffic is not None, 'traffic spawn failed')
        owned.append(traffic)
        adapter.set_halt_route(ego, scene['vehicle_route_xy'], case.activity)
        adapter.set_traffic_route(traffic, scene['traffic_route_xy'])
        adapter.set_exception_context(case.exception, scene.get('authority_record_id'),
                                      scene.get('conflicting_traffic_id'))
        return {'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    first_frame = rows[0].get('original_frame')
    first_time = rows[0].get('time_s')
    require(type(first_frame) is int and number(first_time),
            'original frame/time identity missing')
    actor_ids = set()
    distances = []
    between = []
    speeds = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first_frame + i and
                number(row.get('time_s')) and abs(row['time_s'] - first_time - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('frame', 'vehicle_motion', 'vehicle_body', 'zone', 'curb',
                      'activity', 'exception', 'traffic_motion'):
            require(row.get(field + '_source_sha256'), 'original frame source missing: ' + field)
        require(row.get('zone_source_sha256') == scene['zone_source_sha256'] and
                row.get('curb_source_sha256') == scene['curb_source_sha256'] and
                row.get('activity') == case.activity and row.get('exception') == case.exception,
                'original zone or activity changed')
        require(row.get('vehicle_id') and row.get('traffic_id') and
                row['vehicle_id'] != row['traffic_id'], 'original participants missing')
        actor_ids.add((row['vehicle_id'], row['traffic_id']))
        require(rectangle(row.get('vehicle_body_rect_m')) and
                number(row.get('vehicle_speed_mps')) and row['vehicle_speed_mps'] >= 0,
                'original vehicle body or speed missing')
        require(number(row.get('traffic_speed_mps')) and row['traffic_speed_mps'] >= 0,
                'original traffic motion missing')
        center = body_center(row['vehicle_body_rect_m'])
        calculated = signed_end_station(center, scene['west_end_curb_point_m'],
                                        scene['east_end_curb_point_m'], case.end)
        require(number(row.get('signed_end_station_m')) and
                abs(row['signed_end_station_m'] - calculated) <= .001,
                'signed end station differs from original body')
        require(row.get('between_zone_curb') == between_zone_curb(
            row['vehicle_body_rect_m'], scene['zone_rect_m'], scene['adjacent_curb_y_m']),
            'between-zone-and-curb classification differs from body')
        distances.append(calculated)
        between.append(row['between_zone_curb'])
        speeds.append(row['vehicle_speed_mps'])
    require(len(actor_ids) == 1, 'original participant identity changed')
    require(min(speeds) <= .1, 'terminal halt never observed')
    require(max(row['traffic_speed_mps'] for row in rows) > 0,
            'traffic actor movement never observed')
    return {'case_id': case.case_id, 'frame_count': len(rows),
            'minimum_signed_end_station_m': min(distances),
            'maximum_signed_end_station_m': max(distances),
            'terminal_between_zone_and_curb': between[-1],
            'terminal_signed_end_station_m': distances[-1],
            'statutory_distance_reference_m': THIRTY_FT_M,
            'legal_judgment': None}
