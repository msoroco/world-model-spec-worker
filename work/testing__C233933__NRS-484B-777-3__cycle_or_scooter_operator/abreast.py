"""Source-gated rider formation probes for NRS 484B.777(3)."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    riders: int
    exclusive: bool
    roadway: bool


CASES = (
    Case('three_roadway_general', 3, False, True),
    Case('two_roadway_general', 2, False, True),
    Case('three_roadway_exclusive', 3, True, True),
    Case('three_path_exclusive', 3, True, False),
)


SOURCES = ('highway_status', 'roadway_boundary', 'shoulder_boundary',
           'rider_occupancy', 'exclusive_use_designation',
           'bicycle_classification', 'moped_exclusion', 'sidewalk_absence',
           'ego_identity', 'control_identity', 'companions_identity',
           'rider_motion', 'formation_geometry')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(v):
    return type(v) in (int, float) and isfinite(v)


def point(v):
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(number(x) for x in v)


def rect(v):
    return (isinstance(v, (list, tuple)) and len(v) == 4 and
            all(number(x) for x in v) and v[0] < v[2] and v[1] < v[3])


def inside(p, bounds):
    return bounds[0] <= p[0] <= bounds[2] and bounds[1] <= p[1] <= bounds[3]


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact rider case')
    require(scene.get('cell_id') == 'C233933' and
            scene.get('actor') == 'cycle_or_scooter_operator' and
            scene.get('highway') is True and
            scene.get('sidewalk_absent') is True,
            'cell/actor/highway/sidewalk context missing')
    require(scene.get('exclusive') is case.exclusive and
            scene.get('roadway') is case.roadway,
            'exclusive-use or roadway context changed')
    ids = scene.get('rider_ids')
    require(isinstance(ids, list) and len(ids) == case.riders and
            len(set(ids)) == len(ids) and all(isinstance(x, str) and x for x in ids),
            'rider identity/count missing')
    require(scene.get('ego_id') == ids[0] and
            scene.get('control_id') == ids[1],
            'ego and control rider not distinct')
    require(scene.get('vehicle_type') == 'human_powered_bicycle' and
            scene.get('moped') is False,
            'qualifying bicycle classification missing')
    for name in SOURCES:
        require(scene.get(name + '_source_sha256'),
                'independent source missing: ' + name)
    require(rect(scene.get('roadway_rect_m')) and
            rect(scene.get('shoulder_rect_m')) and
            rect(scene.get('occupied_surface_rect_m')),
            'roadway/shoulder/occupied surface geometry missing')
    routes = scene.get('rider_routes_xy')
    require(isinstance(routes, list) and len(routes) == case.riders and
            all(isinstance(route, list) and len(route) >= 2 and
                all(point(p) for p in route) for route in routes),
            'rider routes missing')
    for route in routes:
        require(all(inside(p, scene['occupied_surface_rect_m']) for p in route),
                'source rider route leaves occupied surface')
        if case.roadway:
            require(all(inside(p, scene['roadway_rect_m']) and
                        not inside(p, scene['shoulder_rect_m']) for p in route),
                    'source roadway rider route enters shoulder')
    for points in zip(*routes):
        require(max(p[0] for p in points) - min(p[0] for p in points) <= .25 and
                max(p[1] for p in points) > min(p[1] for p in points),
                'source rider routes cannot produce planned physical formation')
    return {'case_id': case.name, 'abreast_legal_judgment': None,
            'exclusive_use_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        for rider_id, route in zip(scene['rider_ids'], scene['rider_routes_xy']):
            actor = adapter.spawn_bicycle(rider_id, route[0])
            require(actor is not None, 'rider spawn failed')
            owned.append(actor)
            adapter.set_route(actor, route)
        return {'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    first = rows[0].get('original_frame')
    t0 = rows[0].get('time_s')
    require(type(first) is int and number(t0), 'original frame/time missing')
    max_longitudinal_spread = 0.
    min_lateral_spread = float('inf')
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - t0 - i / 20) <= .005,
                'original frame/time join invalid')
        for name in SOURCES:
            require(row.get(name + '_source_sha256') ==
                    scene[name + '_source_sha256'],
                    'original source changed: ' + name)
        require(row.get('rider_ids') == scene['rider_ids'] and
                row.get('exclusive') is case.exclusive and
                row.get('roadway') is case.roadway,
                'rider or occupied-surface context changed')
        positions = row.get('rider_xy')
        require(isinstance(positions, list) and
                len(positions) == case.riders and
                all(point(p) for p in positions),
                'original rider positions missing')
        require(all(inside(p, scene['occupied_surface_rect_m']) for p in positions),
                'rider left occupied surface')
        if case.roadway:
            require(all(inside(p, scene['roadway_rect_m']) and
                        not inside(p, scene['shoulder_rect_m'])
                        for p in positions),
                    'roadway rider entered shoulder or left roadway')
        speeds = row.get('rider_speed_mps')
        require(isinstance(speeds, list) and
                len(speeds) == case.riders and
                all(number(v) and v >= 0 for v in speeds),
                'original rider motion missing')
        longitudinal = max(p[0] for p in positions) - min(p[0] for p in positions)
        lateral = max(p[1] for p in positions) - min(p[1] for p in positions)
        max_longitudinal_spread = max(max_longitudinal_spread, longitudinal)
        min_lateral_spread = min(min_lateral_spread, lateral)
    require(min_lateral_spread > 0 and max_longitudinal_spread <= .25,
            'planned side-by-side physical formation not realized')
    return {'case_id': case.name, 'rider_count': case.riders,
            'max_longitudinal_spread_m': max_longitudinal_spread,
            'min_lateral_spread_m': min_lateral_spread,
            'abreast_legal_judgment': None,
            'exclusive_use_judgment': None}
