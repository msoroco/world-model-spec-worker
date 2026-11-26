"""Source-gated cycle/motor-vehicle passing probes for NRS 484B.270(7)(b).

Physical clearance, closing and pass history are measurements, not legal
safety or endangerment thresholds.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    cycle_kind: str
    lateral_offset_m: float
    pass_policy: str


CASES = (
    Case('bicycle_wider_pass', 'bicycle', 2.5, 'complete'),
    Case('bicycle_closer_pass', 'bicycle', 1.5, 'complete'),
    Case('bicycle_abort', 'bicycle', 2.5, 'abort'),
    Case('electric_bicycle_pass', 'electric_bicycle', 2.5, 'complete'),
    Case('electric_scooter_pass', 'electric_scooter', 2.5, 'complete'),
    Case('endangerment_offset_low', 'bicycle', 1.5, 'complete'),
    Case('endangerment_offset_high', 'bicycle', 2.5, 'complete'),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(x):
    return type(x) in (int, float) and isfinite(x)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact passing case')
    require(scene.get('cell_id') == 'C229023' and
            scene.get('actor') == 'cycle_or_scooter_operator',
            'wrong exact cell or actor')
    require(scene.get('cycle_kind') == case.cycle_kind and
            scene.get('moped') is False and
            scene.get('other_is_motor_vehicle') is True,
            'qualifying actor/other vehicle context missing')
    require(scene.get('human_operator') is True and
            scene.get('other_occupant_count') >= 1 and
            len(scene.get('other_occupant_ids', [])) == scene['other_occupant_count'],
            'operator or motor-vehicle occupants missing')
    for field in ('jurisdiction', 'road_geometry', 'cycle_classification',
                  'wheel_arrangement', 'wheel_diameter', 'moped_exclusion',
                  'operator_control', 'motor_vehicle_classification',
                  'motor_vehicle_occupants', 'passing_side', 'route_geometry'):
        require(scene.get(field + '_source_sha256'),
                'original passing source missing: ' + field)
    if case.cycle_kind == 'bicycle':
        require(scene.get('human_powered') is True and
                number(scene.get('wheel_diameter_m')) and
                scene['wheel_diameter_m'] > 0,
                'human-powered bicycle wheel context missing')
    for key in ('cycle_route_xy', 'motor_route_xy'):
        route = scene.get(key)
        require(isinstance(route, list) and len(route) >= 2 and
                all(isinstance(p, list) and len(p) == 2 and
                    all(number(v) for v in p) for p in route),
                key + ' missing')
    require(scene['cycle_route_xy'][0][0] < scene['motor_route_xy'][0][0],
            'cycle must start behind motor vehicle')
    return {'cycle_kind': case.cycle_kind, 'other_occupants':
            tuple(scene['other_occupant_ids']), 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        cycle = adapter.spawn_cycle(scene['cycle_route_xy'][0], case.cycle_kind)
        require(cycle is not None, 'cycle spawn failed')
        owned.append(cycle)
        motor = adapter.spawn_motor_vehicle(scene['motor_route_xy'][0],
                                            scene['other_occupant_ids'])
        require(motor is not None, 'motor vehicle spawn failed')
        owned.append(motor)
        adapter.set_motor_route(motor, scene['motor_route_xy'])
        adapter.set_pass_route(cycle, scene['cycle_route_xy'],
                               lateral_offset_m=case.lateral_offset_m,
                               pass_policy=case.pass_policy)
        return {'case_id': case.case_id, 'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame pass capture missing')
    start = rows[0].get('original_frame')
    require(type(start) is int, 'original frame identity missing')
    cycle_id = motor_id = None
    relative = []
    clearances = []
    closing = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == start + i and number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('source', 'cycle_motion', 'motor_motion', 'body_geometry',
                      'occupants', 'surface_clearance', 'route'):
            require(row.get(field + '_sha256'), 'original source missing: ' + field)
        require(row.get('road_geometry_source_sha256') ==
                scene['road_geometry_source_sha256'] and
                row.get('cycle_kind') == case.cycle_kind and
                row.get('other_occupant_ids') == scene['other_occupant_ids'],
                'original participant/road context changed')
        require(row.get('cycle_id') and row.get('motor_id'),
                'participant identity missing')
        cycle_id = cycle_id or row['cycle_id']
        motor_id = motor_id or row['motor_id']
        require(row['cycle_id'] == cycle_id and row['motor_id'] == motor_id and
                cycle_id != motor_id, 'participant identity changed')
        for field in ('cycle_station_m', 'motor_station_m', 'cycle_speed_mps',
                      'motor_speed_mps', 'surface_clearance_m'):
            require(number(row.get(field)), 'original physical stream missing: ' + field)
        require(row['surface_clearance_m'] >= 0,
                'physical surface collision/overlap reported')
        relative.append(row['cycle_station_m'] - row['motor_station_m'])
        clearances.append(row['surface_clearance_m'])
        closing.append(row['cycle_speed_mps'] - row['motor_speed_mps'])
    require(relative[0] < 0, 'cycle did not approach from behind')
    require(any(abs(v) <= 1 for v in relative), 'alongside phase absent')
    if case.pass_policy == 'complete':
        require(relative[-1] > 0, 'cycle did not clear ahead')
    else:
        require(relative[-1] <= 0, 'abort case completed pass')
    return {'case_id': case.case_id, 'frame_count': 900,
            'cycle_kind': case.cycle_kind,
            'requested_lateral_offset_m': case.lateral_offset_m,
            'pass_policy': case.pass_policy,
            'road_geometry_source_sha256': scene['road_geometry_source_sha256'],
            'initial_relative_station_m': relative[0],
            'terminal_relative_station_m': relative[-1],
            'minimum_surface_clearance_m': min(clearances),
            'maximum_closing_speed_mps': max(closing),
            'other_occupant_ids': list(scene['other_occupant_ids']),
            'safe_pass_judgment': None, 'endangerment_judgment': None,
            'legal_judgment': None}
