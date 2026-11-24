"""Source-gated one-way road motion probe for NRS 484B.220(1)."""
from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    lane: int
    direction: str


CASES = (
    Case('designated', 1, 'designated'),
    Case('opposed_reverse', 1, 'opposed'),
    Case('lane2_designated', 2, 'designated'),
    Case('lane2_opposed_reverse', 2, 'opposed'),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def point(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2 and
            all(number(v) for v in value))


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact one-way case')
    require(scene.get('cell_id') == 'C147311' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('motor_vehicle') is True and
            scene.get('driver_in_physical_control') is True,
            'driver/vehicle context missing')
    require(scene.get('public_highway') is True and
            scene.get('highway_dedicated') is True and
            scene.get('one_way_designated') is True and
            scene.get('lane_count') >= 2,
            'multilane one-way highway missing')
    require(scene.get('lane') == case.lane and
            scene.get('direction') == case.direction,
            'case variables changed')
    require(scene.get('sign_authorized') is True and
            scene.get('signposted') is True and
            scene.get('sign_governs_route') is True,
            'authorized governing one-way sign missing')
    for field in ('highway', 'vehicle', 'driver_control',
                  'lane_inventory', 'one_way_designation',
                  'sign_authority', 'sign_message', 'sign_orientation',
                  'sign_placement', 'sign_governance', 'ego_route'):
        require(scene.get(field + '_source_sha256'),
                'original context missing: ' + field)
    direction = scene.get('designated_unit_xy')
    require(point(direction) and abs(hypot(*direction)-1) <= .001,
            'designated direction unit vector missing')
    route = scene.get('ego_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(point(p) for p in route), 'vehicle route missing')
    require(scene.get('lane_ids') and len(scene['lane_ids']) >= 2 and
            case.lane in scene['lane_ids'], 'selected same-direction lane missing')
    return {'case_id': case.name, 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        adapter.place_one_way_sign(scene['sign_xy'],
                                   scene['designated_unit_xy'])
        ego = adapter.spawn_vehicle(scene['ego_route_xy'][0], case.lane)
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        adapter.set_route(ego, scene['ego_route_xy'], case.direction)
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
    ego_id = None
    forward = reverse = 0
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('frame', 'ego_motion', 'driver_control',
                      'lane_inventory', 'one_way_designation',
                      'sign_authority', 'sign_message',
                      'sign_orientation', 'sign_governance'):
            require(row.get(field + '_source_sha256'),
                    'original measurement source missing: ' + field)
        require(row.get('one_way_designation_source_sha256') ==
                scene['one_way_designation_source_sha256'] and
                row.get('sign_governance_source_sha256') ==
                scene['sign_governance_source_sha256'] and
                row.get('lane') == case.lane and
                row.get('sign_governs_route') is True,
                'original lane/designation/sign context changed')
        require(row.get('ego_id'), 'ego identity missing')
        ego_id = ego_id or row['ego_id']
        require(row['ego_id'] == ego_id and point(row.get('velocity_xy')),
                'ego identity or velocity missing')
        dot = sum(a*b for a,b in zip(row['velocity_xy'],
                                     scene['designated_unit_xy']))
        if dot > .5:
            forward += 1
        elif dot < -.5:
            reverse += 1
    require(forward + reverse >= 100, 'original vehicle travel missing')
    require((forward > reverse) if case.direction == 'designated'
            else (reverse > forward),
            'requested actual travel direction not observed')
    return {'case_id': case.name, 'frame_count': 900,
            'forward_moving_frames': forward,
            'reverse_moving_frames': reverse,
            'actual_direction': 'designated' if forward > reverse else 'opposed',
            'legal_judgment': None}
