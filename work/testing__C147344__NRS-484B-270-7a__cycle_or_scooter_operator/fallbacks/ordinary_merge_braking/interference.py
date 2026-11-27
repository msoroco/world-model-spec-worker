"""Source-gated electric-bicycle and motor-vehicle interaction.

The observations describe physical motion. An authored intention declaration is
kept separate and never inferred from a trajectory or braking outcome.
"""

from dataclasses import dataclass
from math import isfinite


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and isfinite(value)


@dataclass(frozen=True)
class Case:
    suffix: str
    bicycle_path: str
    motor_response: str
    authored_target: str | None


CASES = (
    Case('planned_merge_braking', 'merge', 'brake', 'impede_motor_vehicle'),
    Case('planned_merge_no_braking', 'merge', 'continue', 'impede_motor_vehicle'),
    Case('ordinary_merge_braking', 'merge', 'brake', None),
    Case('hold_lane_braking', 'hold', 'brake', None),
)


def validate_scene(scene, case):
    require(case in CASES, 'unknown exact interference case')
    require(scene.get('cell_id') == 'C147344' and
            scene.get('actor') == 'cycle_or_scooter_operator' and
            scene.get('law_id') == 'NRS-484B-270-7a',
            'wrong law, cell or actor')
    require(scene.get('road_layout') == 'one_way_multilane' and
            scene.get('maneuver') == 'travel', 'wrong fixed cell geometry')
    classification = scene.get('electric_bicycle', {})
    require(classification.get('class') == 1 and
            classification.get('fully_operable_pedals') is True and
            classification.get('saddle') is True and
            classification.get('moped') is False and
            classification.get('electric_scooter') is False and
            finite(classification.get('motor_watts')) and
            0 < classification['motor_watts'] <= 750 and
            classification.get('assistance_only_while_pedaling') is True and
            classification.get('assistance_ceases_at_mph') == 20 and
            finite(classification.get('wheel_diameter_m')) and
            classification['wheel_diameter_m'] > 0,
            'qualifying Class 1 electric bicycle source missing')
    require(scene.get('motor_vehicle', {}).get('statutory_motor_vehicle') is True and
            scene['motor_vehicle'].get('vehicle_id') and
            scene.get('bicycle_id') and
            scene['bicycle_id'] != scene['motor_vehicle']['vehicle_id'],
            'distinct statutory motor vehicle source missing')
    for name in ('reviewed_road', 'electric_bicycle_classification',
                 'motor_vehicle_classification', 'route_geometry',
                 'operator_control', 'authored_plan'):
        require(scene.get(name + '_source_sha256'),
                'original source missing: ' + name)
    require(scene.get('bicycle_path') == case.bicycle_path and
            scene.get('motor_response') == case.motor_response,
            'case control differs from reviewed scene')
    plan = scene.get('intention_declaration')
    if case.authored_target is None:
        require(plan is None, 'unplanned control cannot carry authored intent')
    else:
        require(isinstance(plan, dict) and
                plan.get('actor_id') == scene['bicycle_id'] and
                plan.get('target_id') == scene['motor_vehicle']['vehicle_id'] and
                plan.get('value') == case.authored_target and
                plan.get('source_sha256') == scene['authored_plan_source_sha256'] and
                plan.get('start_frame') == 0 and
                plan.get('end_frame') == 599,
                'source-bound authored intent declaration missing')
    routes = scene.get('routes', {})
    for name in ('bicycle', 'motor_vehicle'):
        points = routes.get(name)
        require(isinstance(points, list) and len(points) >= 2 and
                all(isinstance(point, list) and len(point) == 2 and
                    all(finite(value) for value in point) for point in points),
                name + ' route source missing')
    require(scene.get('lane_assignments') ==
            {'bicycle_initial': 'right', 'motor_initial': 'middle'},
            'fixed lane assignments missing')
    return True


def construct(adapter, scene, case):
    """Spawn both participants and request a route; actual movement is read back."""
    validate_scene(scene, case)
    owned = []
    try:
        require(len(scene['routes']['bicycle']) >= 3,
                'source-approved upstream fallback waypoint missing')
        bicycle_route = scene['routes']['bicycle'][1:]
        bicycle = adapter.spawn_electric_bicycle(
            bicycle_route[0], scene['electric_bicycle'])
        require(bicycle is not None, 'electric bicycle spawn failed')
        owned.append(bicycle)
        motor = adapter.spawn_motor_vehicle(
            scene['routes']['motor_vehicle'][0], scene['motor_vehicle'])
        require(motor is not None, 'motor vehicle spawn failed')
        owned.append(motor)
        adapter.set_motor_route(motor, scene['routes']['motor_vehicle'],
                                response=case.motor_response)
        adapter.set_bicycle_route(bicycle, bicycle_route,
                                  path=case.bicycle_path)
        return {'bicycle': bicycle, 'motor_vehicle': motor,
                'owned': tuple(owned), 'declared_intention':
                scene.get('intention_declaration')}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows, scene, case):
    """Measure all 600 original samples without assigning a legal verdict."""
    validate_scene(scene, case)
    require(len(rows) == 600, 'original 600-frame readback missing')
    first = rows[0].get('original_frame')
    require(type(first) is int, 'original frame identity missing')
    motor_speeds, motor_brakes, gaps, bicycle_lanes = [], [], [], []
    for index, row in enumerate(rows):
        require(row.get('original_frame') == first + index and
                finite(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - index / 20) <= .005,
                'original frame/time join invalid')
        require(row.get('bicycle_id') == scene['bicycle_id'] and
                row.get('motor_vehicle_id') ==
                scene['motor_vehicle']['vehicle_id'],
                'original participant identity differs')
        for source in ('bicycle_motion', 'motor_motion', 'body_geometry',
                       'lane_geometry', 'motor_control', 'camera_frames'):
            require(row.get(source + '_sha256'),
                    'original readback source missing: ' + source)
        for name in ('bicycle_speed_mps', 'motor_speed_mps',
                     'body_gap_m', 'motor_brake'):
            require(finite(row.get(name)), 'original value missing: ' + name)
        require(0 <= row['motor_brake'] <= 1, 'invalid motor brake readback')
        require(row.get('bicycle_lane') in ('right', 'middle') and
                row.get('motor_lane') == 'middle',
                'original lane assignment differs')
        motor_speeds.append(row['motor_speed_mps'])
        motor_brakes.append(row['motor_brake'])
        gaps.append(row['body_gap_m'])
        bicycle_lanes.append(row['bicycle_lane'])
    require(max(motor_speeds) > 0.1, 'separate motor vehicle never moved')
    require(bicycle_lanes[0] == 'right', 'bicycle origin lane differs')
    if case.bicycle_path == 'merge':
        require('middle' in bicycle_lanes[200:],
                'intended merge did not physically occur')
    else:
        require(set(bicycle_lanes) == {'right'},
                'hold-lane probe crossed into motor lane')
    return {'frame_count': 600, 'case_id': case.suffix,
            'bicycle_id': scene['bicycle_id'],
            'motor_vehicle_id': scene['motor_vehicle']['vehicle_id'],
            'reviewed_road_source_sha256':
            scene['reviewed_road_source_sha256'],
            'electric_bicycle_classification_source_sha256':
            scene['electric_bicycle_classification_source_sha256'],
            'motor_vehicle_classification_source_sha256':
            scene['motor_vehicle_classification_source_sha256'],
            'route_geometry_source_sha256':
            scene['route_geometry_source_sha256'],
            'requested_bicycle_path': case.bicycle_path,
            'requested_motor_response': case.motor_response,
            'motor_vehicle_moved': True,
            'minimum_body_gap_m': min(gaps),
            'motor_speed_range_mps': [min(motor_speeds), max(motor_speeds)],
            'maximum_motor_brake': max(motor_brakes),
            'bicycle_lane_history': bicycle_lanes,
            'authored_intention_source_sha256':
            scene['authored_plan_source_sha256'],
            'declared_intention': scene.get('intention_declaration'),
            'intent_inferred_from_motion': False,
            'legal_judgment': None}
