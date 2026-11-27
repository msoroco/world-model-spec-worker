"""Source-gated physical observations for NRS 484B.777(1) and (2).

Distances and controller targets are engineering measurements. They do not
define due care, safety, lawful speed, or practicability under the statute.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Case:
    name: str
    cycle_kind: str
    lateral_target_m: float
    right_impediment: str
    narrow_lane: bool
    traffic_speed_context: str
    left_turn_preparation: bool
    target_motion: str


CASES = (
    Case('moving_near_right', 'bicycle', 0.75, 'none', False, 'not_commensurate', False, 'moving'),
    Case('moving_left_offset', 'bicycle', 1.75, 'none', False, 'not_commensurate', False, 'moving'),
    Case('moving_right_impeded', 'bicycle', 1.75, 'moving_vehicle', False, 'not_commensurate', False, 'moving'),
    Case('moving_narrow_lane', 'bicycle', 1.75, 'none', True, 'not_commensurate', False, 'moving'),
    Case('moving_commensurate_speed', 'bicycle', 1.75, 'none', False, 'commensurate_candidate', False, 'moving'),
    Case('moving_left_preparation', 'bicycle', 1.75, 'none', False, 'not_commensurate', True, 'moving'),
    Case('standing_right_impeded', 'bicycle', 1.75, 'standing_vehicle', False, 'not_commensurate', False, 'standing'),
    Case('scooter_right_impeded', 'electric_scooter', 1.75, 'moving_vehicle', False, 'not_commensurate', False, 'moving'),
)

SOURCE_ROLES = (
    'road_geometry', 'roadway_boundary', 'right_side_boundary', 'lane_width',
    'cycle_classification', 'operator_control', 'other_vehicle_classification',
    'other_vehicle_motion', 'route_geometry', 'passing_side', 'surface_hazards',
    'nearby_traffic', 'left_turn_preparation', 'lawful_speed_basis',
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and isfinite(value)


def point(value):
    return isinstance(value, list) and len(value) == 2 and all(finite(x) for x in value)


def validate_scene(scene, case):
    need(case in CASES, 'unknown exact right-side case')
    need(scene.get('cell_id') == 'C229023' and scene.get('actor') == 'cycle_or_scooter_operator',
         'exact cell or actor differs')
    need(scene.get('roadway_occupied') is True and scene.get('shoulder_occupied') is False,
         'roadway occupation excluding shoulder missing')
    need(scene.get('cycle_kind') == case.cycle_kind and scene.get('human_operator') is True,
         'covered cycle or operator missing')
    need(scene.get('moped') is False and scene.get('other_is_motor_vehicle') is True,
         'covered cycle and distinct vehicle classification missing')
    need(scene.get('other_vehicle_id') and scene.get('cycle_id') and
         scene['other_vehicle_id'] != scene['cycle_id'], 'distinct passing participants missing')
    need(scene.get('right_impediment') == case.right_impediment and
         scene.get('narrow_lane') is case.narrow_lane and
         scene.get('traffic_speed_context') == case.traffic_speed_context and
         scene.get('left_turn_preparation') is case.left_turn_preparation and
         scene.get('target_motion') == case.target_motion,
         'declared positioning exception or vehicle motion differs')
    for role in SOURCE_ROLES:
        need(isinstance(scene.get(role + '_source_sha256'), str) and
             len(scene[role + '_source_sha256']) == 64,
             'reviewed source missing: ' + role)
    for field in ('roadway_right_y_m', 'lane_width_m', 'cycle_body_half_width_m',
                  'other_body_half_width_m'):
        need(finite(scene.get(field)), 'road geometry or body dimension missing: ' + field)
    need(scene['lane_width_m'] > 2 * scene['cycle_body_half_width_m'] > 0 and
         scene['other_body_half_width_m'] > 0,
         'roadway or body dimensions infeasible')
    need(scene.get('passing_side') in ('left', 'right'), 'passing side missing')
    for field in ('cycle_route_xy', 'other_route_xy'):
        route = scene.get(field)
        need(isinstance(route, list) and len(route) >= 2 and all(point(p) for p in route),
             'reviewed route missing: ' + field)
    need(scene['cycle_route_xy'][0][0] < scene['other_route_xy'][0][0],
         'cycle must start behind target')
    need(finite(scene.get('requested_lateral_target_m')) and
         scene['requested_lateral_target_m'] == case.lateral_target_m,
         'requested lateral target changed')
    if case.right_impediment != 'none':
        need(scene.get('right_impediment_id') and
             scene.get('right_impediment_body_bounds_xy') and
             len(scene['right_impediment_body_bounds_xy']) == 4 and
             all(finite(x) for x in scene['right_impediment_body_bounds_xy']),
             'constructed right-side impediment body geometry missing')
    if case.left_turn_preparation:
        need(scene.get('left_turn_intent_actor_id') == scene['cycle_id'] and
             isinstance(scene.get('left_turn_intent_source_sha256'), str),
             'original left-turn preparation declaration missing')
    return {'cycle_kind': case.cycle_kind, 'legal_practicability': None,
            'legal_due_care': None, 'legal_speed_commensurate': None}


def construct(adapter, scene, case):
    context = validate_scene(scene, case)
    owned = []
    try:
        cycle = adapter.spawn_cycle(scene['cycle_route_xy'][0], case.cycle_kind)
        need(cycle is not None, 'cycle spawn failed')
        owned.append(cycle)
        other = adapter.spawn_motor_vehicle(scene['other_route_xy'][0])
        need(other is not None, 'other vehicle spawn failed')
        owned.append(other)
        adapter.set_other_route(other, scene['other_route_xy'], case.target_motion)
        if case.right_impediment != 'none':
            impediment = adapter.spawn_impediment(
                scene['right_impediment_id'], scene['right_impediment_body_bounds_xy'],
                case.right_impediment)
            need(impediment is not None, 'right-side impediment spawn failed')
            owned.append(impediment)
        adapter.set_cycle_route(cycle, scene['cycle_route_xy'],
                                case.lateral_target_m, scene['passing_side'],
                                case.left_turn_preparation)
        return {'case_id': case.name, 'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows, scene, case):
    validate_scene(scene, case)
    need(len(rows) == 900, 'original 900-frame readback missing')
    first = rows[0].get('original_frame')
    t0 = rows[0].get('time_s')
    need(type(first) is int and finite(t0), 'original frame/time missing')
    lateral, clearance, relative, cycle_speed, other_speed = [], [], [], [], []
    prior_ids = None
    for index, row in enumerate(rows):
        need(row.get('original_frame') == first + index and finite(row.get('time_s')) and
             abs(row['time_s'] - t0 - index / 20) <= .005,
             'original 20 Hz frame/time join differs')
        ids = (row.get('cycle_id'), row.get('other_vehicle_id'))
        need(ids == (scene['cycle_id'], scene['other_vehicle_id']) and
             ids[0] != ids[1] and (prior_ids is None or ids == prior_ids),
             'original participant identity differs')
        prior_ids = ids
        for role in SOURCE_ROLES:
            need(row.get(role + '_source_sha256') == scene[role + '_source_sha256'],
                 'original source changed: ' + role)
        for field in ('cycle_station_m', 'other_station_m', 'cycle_center_y_m',
                      'cycle_speed_mps', 'other_speed_mps', 'surface_clearance_m',
                      'right_access_width_m'):
            need(finite(row.get(field)), 'original physical stream missing: ' + field)
        need(row['surface_clearance_m'] >= 0 and row['right_access_width_m'] >= 0,
             'original body/surface geometry overlaps')
        need(row.get('right_impediment_id') == scene.get('right_impediment_id') and
             row.get('left_turn_preparation') is case.left_turn_preparation,
             'original impediment or turn context differs')
        lateral.append(row['cycle_center_y_m'] - scene['roadway_right_y_m'] -
                       scene['cycle_body_half_width_m'])
        clearance.append(row['surface_clearance_m'])
        relative.append(row['cycle_station_m'] - row['other_station_m'])
        cycle_speed.append(row['cycle_speed_mps'])
        other_speed.append(row['other_speed_mps'])
    need(relative[0] < 0 and any(abs(v) <= 1 for v in relative) and relative[-1] > 0,
         'behind-to-alongside-to-ahead pass not observed')
    if case.target_motion == 'moving':
        need(max(other_speed) > 0, 'same-direction target vehicle did not move')
    else:
        need(max(other_speed) <= .05, 'standing target vehicle moved')
    return {'case_id': case.name, 'frame_count': 900,
            'cycle_kind': case.cycle_kind, 'target_motion': case.target_motion,
            'right_impediment': case.right_impediment, 'narrow_lane': case.narrow_lane,
            'traffic_speed_context': case.traffic_speed_context,
            'left_turn_preparation': case.left_turn_preparation,
            'requested_lateral_target_m': case.lateral_target_m,
            'minimum_right_edge_distance_m': min(lateral),
            'minimum_surface_clearance_m': min(clearance),
            'initial_relative_station_m': relative[0],
            'terminal_relative_station_m': relative[-1],
            'mean_cycle_speed_mps': sum(cycle_speed) / len(cycle_speed),
            'mean_other_speed_mps': sum(other_speed) / len(other_speed),
            'road_geometry_source_sha256': scene['road_geometry_source_sha256'],
            'lawful_speed_basis_source_sha256': scene['lawful_speed_basis_source_sha256'],
            'legal_practicability': None, 'legal_due_care': None,
            'legal_speed_commensurate': None, 'legal_safety': None}
