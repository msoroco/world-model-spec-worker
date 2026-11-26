"""Source-gated sloped-highway standing probes for NRS 484B.533."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping
import re


@dataclass(frozen=True)
class Case:
    name: str
    grade: str
    person_action: str
    engine_off: bool
    brake_set: bool
    wheels_toward: bool


CASES = (
    Case('slope_depart_all_set', 'slope', 'depart', True, True, True),
    Case('slope_depart_engine_on', 'slope', 'depart', False, True, True),
    Case('slope_depart_brake_off', 'slope', 'depart', True, False, True),
    Case('slope_depart_wheels_away', 'slope', 'depart', True, True, False),
    Case('slope_person_stays', 'slope', 'stay', False, False, False),
    Case('slope_passenger_exchange', 'slope', 'passenger_exchange', True, True, True),
    Case('flat_depart_all_set', 'flat', 'depart', True, True, True),
)

SCENE_SOURCES = ('highway', 'vehicle', 'grade', 'curb_side', 'engine',
                 'brake_mechanics', 'front_wheels', 'responsible_person',
                 'person_actions', 'standing_interval', 'passenger_activity',
                 'other_vehicle_route')
ROW_SOURCE_JOINS = {
    'grade': 'grade', 'curb_side': 'curb_side', 'engine': 'engine',
    'brake_mechanics': 'brake_mechanics', 'front_wheels': 'front_wheels',
    'responsible_person': 'responsible_person',
    'person_actions': 'person_actions',
    'passenger_activity': 'passenger_activity',
    'other_vehicle_motion': 'other_vehicle_route',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def point(value):
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(number(v) for v in value)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact standing case')
    require(scene.get('cell_id') == 'C276300' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('vehicle_qualifies') is True and
            scene.get('highway_public_access') is True and
            scene.get('highway_dedicated') is True,
            'qualifying highway vehicle missing')
    require(scene.get('grade_kind') == case.grade and
            scene.get('person_action') == case.person_action and
            scene.get('engine_off_request') is case.engine_off and
            scene.get('brake_set_request') is case.brake_set and
            scene.get('wheels_toward_request') is case.wheels_toward,
            'case variables changed')
    for field in SCENE_SOURCES:
        require(isinstance(scene.get(field + '_source_sha256'), str) and
                re.fullmatch('[0-9a-f]{64}', scene[field + '_source_sha256']),
                'original context missing: ' + field)
    require(number(scene.get('grade_percent')) and
            scene['grade_percent'] >= 0 and
            point(scene.get('curb_direction_xy')),
            'grade/curb geometry missing')
    require(scene['curb_direction_xy'] != [0, 0],
            'curb direction zero')
    for field in ('ego_route_xy', 'other_route_xy', 'person_route_xy'):
        route = scene.get(field)
        require(isinstance(route, list) and len(route) >= 2 and
                all(point(p) for p in route), field + ' missing')
    require(scene.get('responsible_person_id') and
            scene.get('other_vehicle_id'), 'participant identity missing')
    return {'case_id': case.name, 'perceptible_grade_judgment': None,
            'unattended_judgment': None, 'effective_brake_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        ego = adapter.spawn_vehicle(scene['ego_route_xy'][0])
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        other = adapter.spawn_vehicle(scene['other_route_xy'][0])
        require(other is not None, 'other vehicle spawn failed')
        owned.append(other)
        person = adapter.spawn_person(scene['person_route_xy'][0])
        require(person is not None, 'person spawn failed')
        owned.append(person)
        adapter.set_standing_route(ego, scene['ego_route_xy'])
        adapter.set_other_route(other, scene['other_route_xy'])
        adapter.set_person_action(person, scene['person_route_xy'], case.person_action)
        adapter.set_engine(ego, not case.engine_off)
        adapter.set_parking_brake(ego, case.brake_set)
        adapter.set_front_wheels(ego, scene['curb_direction_xy'], case.wheels_toward)
        return {'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case,
                     *, diagnostic_fixture: bool = False):
    validate_scene(scene, case)
    require(len(rows) == (9 if diagnostic_fixture else 900),
            'original frame capture missing')
    first = rows[0].get('original_frame')
    require(type(first) is int and number(rows[0].get('time_s')),
            'original frame/time identity missing')
    ego_id = person_id = other_id = None
    standing = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('frame', 'ego_motion', 'grade', 'curb_side', 'engine',
                      'brake_mechanics', 'front_wheels', 'responsible_person',
                      'person_actions', 'passenger_activity', 'other_vehicle_motion'):
            require(row.get(field + '_source_sha256'),
                    'original measurement source missing: ' + field)
        for row_field, scene_field in ROW_SOURCE_JOINS.items():
            require(row.get(row_field + '_source_sha256') ==
                    scene[scene_field + '_source_sha256'],
                    'original source join differs: ' + row_field)
        require(row.get('person_action') == case.person_action,
                'original person context changed')
        require(row.get('ego_id') and row.get('person_id') and
                row.get('other_id'), 'participant identity missing')
        ego_id = ego_id or row['ego_id'];person_id = person_id or row['person_id']
        other_id = other_id or row['other_id']
        require(row['ego_id'] == ego_id and row['person_id'] == person_id and
                row['other_id'] == other_id and len({ego_id, person_id, other_id}) == 3,
                'participant identity changed')
        for field in ('ego_speed_mps', 'engine_rpm', 'brake_torque_nm',
                      'person_distance_m', 'grade_percent', 'other_speed_mps'):
            require(number(row.get(field)) and row[field] >= 0,
                    'original physical stream missing: ' + field)
        require(point(row.get('front_wheel_vector_xy')) and
                type(row.get('brake_engaged')) is bool and
                type(row.get('engine_ignition_on')) is bool,
                'wheel/brake/engine state missing')
        if row['ego_speed_mps'] <= .01:
            dot = sum(a*b for a,b in zip(row['front_wheel_vector_xy'],
                                         scene['curb_direction_xy']))
            standing.append((row, dot))
    require(len(standing) >= (2 if diagnostic_fixture else 20),
            'standing interval missing')
    require(any(row['person_distance_m'] >= 2 for row,_ in standing)
            if case.person_action == 'depart' else True,
            'person departure not observed')
    require(all(row['engine_ignition_on'] is not case.engine_off for row,_ in standing)
            and all(row['brake_engaged'] is case.brake_set for row,_ in standing)
            and all((dot > 0) is case.wheels_toward for _,dot in standing),
            'requested preparation not measured')
    return {'case_id': case.name, 'standing_frame_count': len(standing),
            'max_person_distance_m': max(row['person_distance_m'] for row,_ in standing),
            'min_brake_torque_nm': min(row['brake_torque_nm'] for row,_ in standing),
            'max_engine_rpm': max(row['engine_rpm'] for row,_ in standing),
            'grade_percent': standing[0][0]['grade_percent'],
            'perceptible_grade_judgment': None,
            'unattended_judgment': None,
            'effective_brake_judgment': None}
