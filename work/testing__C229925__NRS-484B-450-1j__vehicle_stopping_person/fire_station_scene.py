"""Exact fire-station entrance constructions; distances remain observations."""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


ASSIGNMENT = 'testing__C229925__NRS-484B-450-1j__vehicle_stopping_person'
LAW = 'NRS-484B-450-1j'


@dataclass(frozen=True)
class Case:
    name: str
    side: str
    activity: str
    distance_ft: int
    circumstance: str

    @property
    def case_id(self):
        return ASSIGNMENT + '__' + self.name


CASES = (
    Case('opposite_stop_74ft', 'opposite', 'stop', 74, 'none'),
    Case('opposite_stop_75ft', 'opposite', 'stop', 75, 'none'),
    Case('opposite_stop_76ft', 'opposite', 'stop', 76, 'none'),
    Case('opposite_stand_74ft', 'opposite', 'stand', 74, 'none'),
    Case('opposite_park_74ft', 'opposite', 'park', 74, 'none'),
    Case('entrance_stop_19ft', 'entrance', 'stop', 19, 'none'),
    Case('entrance_stop_20ft', 'entrance', 'stop', 20, 'none'),
    Case('entrance_stop_21ft', 'entrance', 'stop', 21, 'none'),
    Case('opposite_stop_traffic_conflict', 'opposite', 'stop', 74, 'traffic_conflict'),
    Case('opposite_stop_law', 'opposite', 'stop', 74, 'law_compliance'),
    Case('opposite_stop_police', 'opposite', 'stop', 74, 'police_direction'),
    Case('opposite_stop_device', 'opposite', 'stop', 74, 'official_device_direction'),
    Case('opposite_stop_nonfire', 'opposite', 'stop', 74, 'non_fire_station'),
    Case('opposite_stop_private_road', 'opposite', 'stop', 74, 'private_road'),
    Case('entrance_stop_74ft', 'entrance', 'stop', 74, 'none'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_pair(value):
    return (isinstance(value, list) and len(value) == 2 and
            all(type(x) in (int, float) and isfinite(x) for x in value))


def signed_side(point, origin, forward):
    return forward[0] * (point[1] - origin[1]) - forward[1] * (point[0] - origin[0])


def point_segment_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    require(length2 > .01, 'fire-station entrance has no width')
    fraction = max(0.0, min(1.0, ((point[0]-start[0])*dx +
                                    (point[1]-start[1])*dy) / length2))
    return hypot(point[0]-start[0]-fraction*dx,
                 point[1]-start[1]-fraction*dy)


def case_by_id(case_id):
    return next((case for case in CASES if case.case_id == case_id), None)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unrecognized exact fire-station case')
    require(scene.get('law_id') == LAW and scene.get('cell_id') == 'C229925' and
            scene.get('actor') == 'vehicle_stopping_person' and
            scene.get('vehicle_class') == 'vehicle' and
            scene.get('stopping_person_id'), 'fire-station case identity missing')
    require(scene.get('side_request') == case.side and
            scene.get('activity_request') == case.activity and
            scene.get('circumstance_request') == case.circumstance and
            scene.get('nominal_entrance_distance_ft') == case.distance_ft,
            'exact case variables changed')
    for key in ('entrance_start_xy', 'entrance_end_xy', 'road_origin_xy',
                'road_forward_xy', 'vehicle_start_xy', 'vehicle_target_xy'):
        require(finite_pair(scene.get(key)), 'reviewed geometry missing: ' + key)
    for key in ('station_identity_source', 'entrance_boundary_source',
                'highway_boundary_source', 'highway_dedication_source',
                'public_vehicular_use_source', 'entrance_side_source',
                'stopping_person_source', 'halt_purpose_source',
                'traffic_conflict_source', 'law_direction_source',
                'police_direction_source', 'official_device_direction_source'):
        require(scene.get(key), 'independent source missing: ' + key)
    forward = scene['road_forward_xy']
    require(abs(hypot(*forward)-1.0) <= .02, 'road direction must be unit length')
    start, end = scene['entrance_start_xy'], scene['entrance_end_xy']
    point_segment_distance(start, start, end)
    entrance = [(start[0]+end[0])/2, (start[1]+end[1])/2]
    entrance_side = signed_side(entrance, scene['road_origin_xy'], forward)
    target_side = signed_side(scene['vehicle_target_xy'], scene['road_origin_xy'], forward)
    require(abs(entrance_side) >= .5 and abs(target_side) >= .5,
            'entrance or vehicle side ambiguous')
    require((entrance_side * target_side < 0) == (case.side == 'opposite'),
            'vehicle did not occupy requested highway side')
    target_distance = point_segment_distance(scene['vehicle_target_xy'], start, end)
    require(abs(target_distance-case.distance_ft*.3048) <= 1.0,
            'nominal target distance disagrees with reviewed geometry')
    require(hypot(scene['vehicle_start_xy'][0]-scene['vehicle_target_xy'][0],
                  scene['vehicle_start_xy'][1]-scene['vehicle_target_xy'][1]) >= 5,
            'approach route cannot reach terminal halt')
    require(scene.get('station_is_fire') is (case.circumstance != 'non_fire_station') and
            scene.get('highway_public_use') is (case.circumstance != 'private_road'),
            'station or public-highway control changed')
    require(scene.get('highway_dedicated') is True,
            'highway dedication context missing')
    if case.circumstance == 'traffic_conflict':
        require(scene.get('conflicting_vehicle_start_xy') and
                scene.get('conflicting_vehicle_target_xy') and
                scene.get('conflicting_vehicle_blueprint_id', '').startswith('vehicle.'),
                'traffic conflict has no physical vehicle')
    if case.circumstance in ('police_direction', 'official_device_direction',
                             'law_compliance'):
        require(scene.get('authority_record_id'),
                'independent authority record missing')
    require(scene.get('vehicle_blueprint_id', '').startswith('vehicle.'),
            'qualifying vehicle blueprint absent')
    markers = scene.get('entrance_markers')
    require(isinstance(markers, list) and len(markers) >= 2,
            'physical entrance markers absent')
    for marker in markers:
        require(marker.get('blueprint_id', '').startswith('static.') and
                finite_pair(marker.get('xy')), 'entrance marker construction invalid')
    return {'case_id': case.case_id,
            'nominal_target_point_distance_m': target_distance,
            'entrance_side_m': entrance_side, 'target_side_m': target_side,
            'legal_distance_convention': None, 'legal_exception_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    measured = validate_scene(scene, case)
    owned = []
    try:
        adapter.place_entrance(scene['entrance_markers'], scene['entrance_start_xy'],
                               scene['entrance_end_xy'])
        vehicle = adapter.spawn_vehicle(scene['vehicle_start_xy'],
                                        scene['vehicle_blueprint_id'])
        require(vehicle is not None, 'vehicle spawn failed')
        owned.append(vehicle)
        adapter.set_halt_route(vehicle, scene['vehicle_target_xy'], case.activity)
        if case.circumstance == 'traffic_conflict':
            traffic = adapter.spawn_vehicle(scene['conflicting_vehicle_start_xy'],
                                            scene['conflicting_vehicle_blueprint_id'])
            require(traffic is not None and traffic is not vehicle,
                    'conflicting traffic spawn failed')
            owned.append(traffic)
            adapter.set_traffic_route(traffic, scene['conflicting_vehicle_target_xy'])
        adapter.set_context(case.circumstance, scene.get('authority_record_id'),
                            scene.get('stopping_person_id'))
        return {'owned': tuple(owned), **measured}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
