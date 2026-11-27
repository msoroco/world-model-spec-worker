"""Source-bound geometry for the exact NRS 484B.110 travel probes.

The results are physical observations. They are never legal conclusions.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    route: str
    designation: str


CASES = (
    Case('through_zone', 'through', 'active'),
    Case('within_zone', 'within', 'active'),
    Case('beside_zone', 'beside', 'active'),
    Case('through_unverified_designation', 'through', 'unverified'),
)


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def point(value: object) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(
        type(x) in (int, float) and isfinite(x) for x in value
    )


def rectangle(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 4
        and all(type(x) in (int, float) and isfinite(x) for x in value)
        and value[0] < value[2]
        and value[1] < value[3]
    )


def intersection_area(a: list[float], b: list[float]) -> float:
    require(rectangle(a) and rectangle(b), 'original body or zone rectangle missing')
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0.0, min(a[3], b[3]) - max(a[1], b[1])
    )


def center(body: list[float]) -> tuple[float, float]:
    require(rectangle(body), 'original vehicle body rectangle missing')
    return ((body[0] + body[2]) / 2, (body[1] + body[3]) / 2)


def validate_scene(scene: Mapping, case: Case) -> dict:
    require(case in CASES, 'unknown exact safety-zone case')
    require(
        scene.get('cell_id') == 'C412974'
        and scene.get('actor') == 'motor_vehicle_driver'
        and scene.get('driver_present') is True
        and scene.get('motor_vehicle') is True,
        'qualifying driver or motor vehicle missing',
    )
    require(
        scene.get('highway_public_access') is True
        and scene.get('highway_dedicated_public_authority') is True,
        'public highway source context missing',
    )
    require(
        scene.get('zone_designation_status') == case.designation
        and scene.get('route_variant') == case.route,
        'exact route or designation contrast changed',
    )
    zone = scene.get('zone_rect_m')
    require(rectangle(zone), 'physical safety-zone boundary rectangle missing')
    for name in ('vehicle_start_xy', 'vehicle_target_xy'):
        require(point(scene.get(name)), 'motor-vehicle route endpoint missing: ' + name)
    route = scene.get('vehicle_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and all(point(x) for x in route),
            'motor-vehicle route missing')
    require(tuple(route[0]) == tuple(scene['vehicle_start_xy']) and
            tuple(route[-1]) == tuple(scene['vehicle_target_xy']),
            'route endpoint readback differs')
    if case.route == 'through':
        require(route[0][0] < zone[0] and route[-1][0] > zone[2] and
                any(zone[0] < x[0] < zone[2] and zone[1] < x[1] < zone[3] for x in route),
                'through-zone route not constructed')
    elif case.route == 'within':
        require(route[0][0] < zone[0] and zone[0] < route[-1][0] < zone[2] and
                zone[1] < route[-1][1] < zone[3],
                'within-zone route not constructed')
    else:
        require(all(x[1] < zone[1] or x[1] > zone[3] for x in route),
                'beside-zone contrast enters zone')
    for name in ('map', 'highway', 'zone_boundary', 'designation', 'marking',
                 'vehicle', 'driver', 'route'):
        require(scene.get(name + '_source_sha256'), 'original source missing: ' + name)
    if case.designation == 'active':
        require(scene.get('official_pedestrian_exclusive') is True and
                scene.get('marking_or_sign_visible') is True and
                scene.get('designation_interval_s') == [0, 45],
                'official active designation or continuing visibility source missing')
    else:
        require(scene.get('official_pedestrian_exclusive') is None and
                scene.get('designation_interval_s') is None,
                'unverified designation contrast manufactured official status')
    return {'case_id': case.name, 'legal_judgment': None}


def measure_original(rows: list[Mapping], scene: Mapping, case: Case) -> dict:
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    first_frame, first_time = rows[0].get('original_frame'), rows[0].get('time_s')
    require(type(first_frame) is int and type(first_time) in (int, float),
            'original first frame or time missing')
    overlap_frames = []
    center_inside_frames = []
    speeds = []
    actor_ids = set()
    for index, row in enumerate(rows):
        require(row.get('original_frame') == first_frame + index and
                type(row.get('time_s')) in (int, float) and
                abs(row['time_s'] - first_time - index / 20) <= .005,
                'original frame/time join invalid')
        for name in ('frame', 'vehicle_body', 'vehicle_motion', 'zone_boundary',
                     'designation', 'marking_visibility'):
            require(row.get(name + '_source_sha256'), 'original frame source missing: ' + name)
        require(row['zone_boundary_source_sha256'] == scene['zone_boundary_source_sha256'] and
                row['designation_source_sha256'] == scene['designation_source_sha256'],
                'original zone or designation source changed')
        require(row.get('vehicle_id'), 'original motor vehicle identity missing')
        actor_ids.add(row['vehicle_id'])
        body = row.get('vehicle_body_rect_m')
        require(rectangle(body) and type(row.get('vehicle_speed_mps')) in (int, float) and
                row['vehicle_speed_mps'] >= 0,
                'original body or motion missing')
        area = intersection_area(body, scene['zone_rect_m'])
        require(type(row.get('zone_overlap_area_m2')) in (int, float) and
                abs(row['zone_overlap_area_m2'] - area) <= 0.001,
                'zone overlap differs from original vehicle body')
        if area > 0:
            overlap_frames.append(index)
        x, y = center(body)
        if scene['zone_rect_m'][0] < x < scene['zone_rect_m'][2] and scene['zone_rect_m'][1] < y < scene['zone_rect_m'][3]:
            center_inside_frames.append(index)
        speeds.append(row['vehicle_speed_mps'])
    require(len(actor_ids) == 1, 'original motor vehicle identity changed')
    require(max(speeds) > 0.5, 'motor vehicle never moved')
    require(bool(overlap_frames) == (case.route != 'beside'),
            'physical zone encounter differs from exact case')
    if case.route == 'through':
        require(center_inside_frames and max(center_inside_frames) < 899,
                'vehicle did not transit through zone')
    if case.route == 'within':
        require(center_inside_frames and 899 in center_inside_frames,
                'vehicle did not end within zone')
    return {
        'case_id': case.name,
        'frame_count': 900,
        'overlap_frame_count': len(overlap_frames),
        'first_overlap_original_frame': first_frame + overlap_frames[0] if overlap_frames else None,
        'last_overlap_original_frame': first_frame + overlap_frames[-1] if overlap_frames else None,
        'center_inside_frame_count': len(center_inside_frames),
        'terminal_center_within': 899 in center_inside_frames,
        'official_designation_status': case.designation,
        'marking_visibility_unverified': case.designation == 'unverified',
        'legal_judgment': None,
    }
