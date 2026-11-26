"""Railroad grade-crossing left-side physical probes for 484B.213(2)(b).

100 feet is statutory. Body reference and crossing extent are engineering
assumptions retained with original sources, not substituted legal definitions.
"""
from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


FOOT_M = 0.3048


@dataclass(frozen=True)
class Case:
    case_id: str
    target_leading_distance_ft: float
    left_side: bool
    one_way: bool = False


CASES = (
    Case('left_101ft', 101, True),
    Case('left_100ft', 100, True),
    Case('left_99ft', 99, True),
    Case('right_99ft', 99, False),
    Case('left_traversal', -5, True),
    Case('one_way_left_99ft', 99, True, True),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(v):
    return type(v) in (int, float) and isfinite(v)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact rail case')
    require(scene.get('cell_id') == 'C204980' and scene.get('actor') == 'motor_vehicle_driver',
            'wrong exact cell or actor')
    require(scene.get('rail_grade_crossing') is True and
            scene.get('stationary_rail_carrier_person_or_property') is True and
            scene.get('streetcar_rail') is False,
            'qualifying railroad grade crossing not established')
    require(scene.get('one_way_highway') is case.one_way,
            'one-way exception context differs from case')
    for field in ('jurisdiction', 'highway_status', 'one_way_status', 'vehicle',
                  'driver_control', 'rail_carrier', 'rail_grade', 'streetcar_exclusion',
                  'crossing_near_edge', 'crossing_far_edge', 'centerline',
                  'route', 'body_reference'):
        require(scene.get(field + '_source_sha256'),
                'original rail site source missing: ' + field)
    near = scene.get('crossing_near_station_m')
    far = scene.get('crossing_far_station_m')
    require(number(near) and number(far) and near < far,
            'crossing physical extent missing')
    route = scene.get('route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and
                all(number(v) for v in p) for p in route), 'rail approach route missing')
    point = scene.get('centerline_point_xy')
    heading = scene.get('centerline_heading_xy')
    require(isinstance(point, list) and len(point) == 2 and all(number(v) for v in point)
            and isinstance(heading, list) and len(heading) == 2 and all(number(v) for v in heading)
            and hypot(*heading) > .5, 'original centerline geometry missing')
    return {'statutory_approach_distance_ft': 100,
            'crossing_extent_engineering_m': [near, far],
            'body_reference_assumption': 'leading body station at near crossing edge',
            'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        ego = adapter.spawn_vehicle(scene['route_xy'][0], 'ego')
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        target_station = (scene['crossing_near_station_m'] -
                          case.target_leading_distance_ft * FOOT_M)
        adapter.set_rail_route(ego, scene['route_xy'], target_station,
                               left_side=case.left_side)
        return {'case_id': case.case_id, 'owned': tuple(owned),
                'target_leading_station_m': target_station, **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame rail capture missing')
    start = rows[0].get('original_frame')
    require(type(start) is int, 'original frame identity missing')
    identity = None
    distances = []
    traversing = []
    left_samples = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == start + i and number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('source', 'body_geometry', 'motion', 'crossing_geometry',
                      'centerline', 'highway_classification', 'rail_carrier'):
            require(row.get(field + '_sha256'), 'original source missing: ' + field)
        require(row.get('crossing_near_edge_source_sha256') ==
                scene['crossing_near_edge_source_sha256'] and
                row.get('centerline_source_sha256') == scene['centerline_source_sha256'] and
                row.get('one_way_highway') is case.one_way,
                'original crossing/highway context changed')
        require(row.get('ego_id'), 'ego identity missing')
        identity = identity or row['ego_id']
        require(row['ego_id'] == identity, 'ego identity changed')
        for field in ('leading_body_station_m', 'trailing_body_station_m',
                      'body_leftmost_lateral_m', 'body_rightmost_lateral_m',
                      'ego_speed_mps'):
            require(number(row.get(field)), 'original physical stream missing: ' + field)
        require(row['leading_body_station_m'] >= row['trailing_body_station_m'] and
                row['body_leftmost_lateral_m'] >= row['body_rightmost_lateral_m'],
                'body extent order invalid')
        distances.append((scene['crossing_near_station_m'] -
                          row['leading_body_station_m']) / FOOT_M)
        traversing.append(row['leading_body_station_m'] >=
                          scene['crossing_near_station_m'] and
                          row['trailing_body_station_m'] <= scene['crossing_far_station_m'])
        left_samples.append(row['body_leftmost_lateral_m'] > 0)
    target = case.target_leading_distance_ft
    observed = distances[100]
    require(abs(observed - target) <= .25,
            'observed distance differs from diagnostic target')
    require(left_samples[100] is case.left_side,
            'observed left-side state differs from case')
    if target < 0:
        require(traversing[100], 'rail crossing traversal absent')
    return {'case_id': case.case_id, 'frame_count': 900,
            'observed_leading_body_distance_ft': observed,
            'approach_within_100ft_by_assumed_reference': 0 < observed < 100,
            'observed_traversal_at_probe': traversing[100],
            'observed_left_body_extent_at_probe': left_samples[100],
            'one_way_highway_observed': case.one_way,
            'body_reference_assumption': 'leading body to near crossing edge',
            'legal_left_side_judgment': None, 'legal_judgment': None}
