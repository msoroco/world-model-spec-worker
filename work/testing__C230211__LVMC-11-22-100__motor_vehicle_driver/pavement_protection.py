"""Source-gated protected-pavement crossing probes for LVMC 11.22.100."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    protection: str
    route: str
    employee_engaged: bool


CASES = (
    Case('barrier_across_cross', 'barrier_across', 'cross', False),
    Case('barrier_around_cross', 'barrier_around', 'cross', False),
    Case('barrier_across_bypass', 'barrier_across', 'bypass', False),
    Case('warning_person_cross', 'warning_person', 'cross', False),
    Case('warning_sign_cross', 'warning_sign', 'cross', False),
    Case('highway_closed_sign_cross', 'highway_closed_sign', 'cross', False),
    Case('barrier_employee_cross', 'barrier_across', 'cross', True),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def rect(value):
    return (isinstance(value, (list, tuple)) and len(value) == 4 and
            all(number(x) for x in value) and value[0] < value[2] and
            value[1] < value[3])


def inside(point, bounds):
    require(isinstance(point, (list, tuple)) and len(point) == 2 and
            all(number(x) for x in point) and rect(bounds),
            'original position or pavement geometry missing')
    return bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact protection case')
    require(scene.get('cell_id') == 'C230211' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('person_is_driver') is True and
            scene.get('vehicle_qualifies') is True,
            'exact driver/vehicle context missing')
    require(scene.get('municipal_jurisdiction') is True and
            scene.get('pavement_condition') in ('newly_laid', 'repaired') and
            rect(scene.get('pavement_rect_m')),
            'jurisdiction or protected pavement missing')
    require(scene.get('protection') == case.protection and
            scene.get('route_kind') == case.route and
            scene.get('employee_engaged') is case.employee_engaged,
            'case variables changed')
    for field in ('jurisdiction', 'driver', 'vehicle', 'pavement_condition',
                  'pavement_extent', 'protection_geometry',
                  'protection_placement_time', 'vehicle_route',
                  'employment', 'work_activity'):
        require(scene.get(field + '_source_sha256'),
                'original context missing: ' + field)
    if case.employee_engaged:
        require(scene.get('employee_pavement_id') == scene.get('pavement_id') and
                scene.get('work_kind') in ('paving', 'repair') and
                scene.get('work_active') is True,
                'same-pavement active employee exception missing')
    if case.protection.startswith('barrier'):
        require(rect(scene.get('barrier_rect_m')),
                'physical barrier geometry missing')
    elif case.protection == 'warning_person':
        require(scene.get('warning_person_id'), 'warning person missing')
    else:
        require(scene.get('sign_text') in ('do_not_drive_on_pavement',
                                           'highway_closed'), 'warning sign missing')
    route = scene.get('vehicle_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and
                all(number(x) for x in p) for p in route),
            'physical vehicle route missing')
    require(not inside(route[0], scene['pavement_rect_m']),
            'route must approach outside protected pavement')
    return {'case_id': case.name, 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        adapter.mark_pavement(scene['pavement_rect_m'],
                              scene['pavement_condition'])
        if case.protection.startswith('barrier'):
            adapter.place_barrier(scene['barrier_rect_m'], case.protection)
        elif case.protection == 'warning_person':
            person = adapter.spawn_warning_person(scene['warning_person_xy'])
            require(person is not None, 'warning person spawn failed')
            owned.append(person)
        else:
            adapter.place_sign(scene['sign_xy'], scene['sign_text'])
        vehicle = adapter.spawn_vehicle(scene['vehicle_route_xy'][0])
        require(vehicle is not None, 'vehicle spawn failed')
        owned.append(vehicle)
        adapter.set_vehicle_route(vehicle, scene['vehicle_route_xy'])
        return {'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    first = rows[0].get('original_frame')
    require(type(first) is int and number(rows[0].get('time_s')),
            'original frame/time identity missing')
    vehicle_id = None
    visited = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('frame', 'vehicle_motion', 'pavement_condition',
                      'pavement_extent', 'protection_geometry',
                      'protection_placement_time', 'employment', 'work_activity'):
            require(row.get(field + '_source_sha256'),
                    'original measurement source missing: ' + field)
        require(row.get('pavement_extent_source_sha256') ==
                scene['pavement_extent_source_sha256'] and
                row.get('protection') == case.protection and
                row.get('employee_engaged') is case.employee_engaged,
                'original pavement/protection context changed')
        require(row.get('vehicle_id'), 'vehicle identity missing')
        vehicle_id = vehicle_id or row['vehicle_id']
        require(vehicle_id == row['vehicle_id'], 'vehicle identity changed')
        visited.append(inside(row.get('vehicle_position_xy'),
                              scene['pavement_rect_m']))
    require(not visited[0], 'vehicle started inside pavement')
    if case.route == 'cross':
        require(any(visited) and not visited[-1],
                'original protected-pavement crossing missing')
    else:
        require(not any(visited), 'bypass case entered protected pavement')
    return {'case_id': case.name, 'frame_count': 900,
            'entered_protected_pavement': any(visited),
            'first_inside_frame': first + visited.index(True) if any(visited) else None,
            'employee_engaged': case.employee_engaged,
            'legal_judgment': None}
