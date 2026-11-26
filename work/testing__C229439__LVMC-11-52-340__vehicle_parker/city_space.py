"""Source-bound municipal-space parking probes for LVMC 11.52.340."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    city_vehicle: bool
    designated: bool
    posted: bool
    inside_space: bool


CASES = (
    Case('other_vehicle_designated_posted', False, True, True, True),
    Case('city_vehicle_designated_posted', True, True, True, True),
    Case('other_vehicle_undesignated', False, False, True, True),
    Case('other_vehicle_unposted', False, True, False, True),
    Case('other_vehicle_adjacent_space', False, True, True, False),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(v):
    return type(v) in (int, float) and isfinite(v)


def point(v):
    return isinstance(v, (tuple, list)) and len(v) == 2 and all(number(x) for x in v)


def rectangle(v):
    return (isinstance(v, (tuple, list)) and len(v) == 4 and
            all(number(x) for x in v) and v[0] < v[2] and v[1] < v[3])


def inside(point_xy, bounds):
    require(point(point_xy) and rectangle(bounds), 'parking geometry missing')
    return bounds[0] <= point_xy[0] <= bounds[2] and bounds[1] <= point_xy[1] <= bounds[3]


def footprint_relation(footprint, governed):
    """Preserve complete body geometry; a center point cannot prove parking position."""
    require(rectangle(footprint) and rectangle(governed),
            'original parking footprint or governed space missing')
    left = max(footprint[0], governed[0])
    right = min(footprint[2], governed[2])
    bottom = max(footprint[1], governed[1])
    top = min(footprint[3], governed[3])
    overlap = max(0., right - left) * max(0., top - bottom)
    return {'overlap_area_m2': overlap,
            'fully_inside': (footprint[0] >= governed[0] and
                             footprint[1] >= governed[1] and
                             footprint[2] <= governed[2] and
                             footprint[3] <= governed[3])}


SOURCE_FIELDS = ('vehicle_identity', 'city_vehicle_authority', 'city_location',
                 'council_designation', 'posted_or_marked_authority',
                 'device_exact_instruction', 'governed_space',
                 'space_geometry', 'parking_purpose', 'loading_activity',
                 'vehicle_motion', 'nrs_definition_scope')


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact City-space case')
    require(scene.get('cell_id') == 'C229439' and
            scene.get('actor') == 'vehicle_parker' and
            scene.get('vehicle_id') and scene.get('parking_person_id'),
            'cell/actor/identity missing')
    require(scene.get('city_location_kind') in ('city_street', 'city_facility'),
            'municipal location missing')
    for key in ('city_vehicle', 'designated', 'posted', 'inside_space'):
        require(scene.get(key) is getattr(case, key), 'case variable changed: ' + key)
    for field in SOURCE_FIELDS:
        require(scene.get(field + '_source_sha256'), 'source missing: ' + field)
    require(rectangle(scene.get('governed_space_rect_m')) and
            rectangle(scene.get('vehicle_footprint_rect_m')),
            'governed space or vehicle footprint missing')
    route = scene.get('parking_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(point(p) for p in route), 'parking route missing')
    require(type(scene.get('park_start_frame')) is int and
            0 <= scene['park_start_frame'] < 900, 'parking interval missing')
    require(scene.get('official_device_text'), 'exact device instruction missing')
    require(scene.get('city_vehicle_authority_ref'),
            'authoritative vehicle status missing; livery is insufficient')
    require(scene.get('council_designation_ref'),
            'Council designation source missing')
    return {'case_id': case.name, 'legal_judgment': None,
            'city_vehicle_scope_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        device = adapter.spawn_device(scene['official_device_text'],
                                      scene['governed_space_rect_m'])
        require(device is not None, 'parking device spawn failed')
        owned.append(device)
        vehicle = adapter.spawn_vehicle(scene['parking_route_xy'][0])
        require(vehicle is not None, 'parking vehicle spawn failed')
        owned.append(vehicle)
        adapter.set_parking_route(vehicle, scene['parking_route_xy'],
                                  scene['park_start_frame'])
        return {'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case,
                     *, diagnostic_frames=None):
    validate_scene(scene, case)
    if diagnostic_frames is None:
        require(len(rows) == 900, 'original 900-frame capture missing')
    else:
        require(3 <= diagnostic_frames <= 9 and len(rows) == diagnostic_frames,
                'synthetic diagnostic frame count differs')
    first = rows[0].get('original_frame')
    t0 = rows[0].get('time_s')
    require(type(first) is int and number(t0), 'original frame/time missing')
    parked = []
    in_space = []
    footprint_overlaps = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - t0 - i / 20) <= .005,
                'original time/frame join invalid')
        for field in SOURCE_FIELDS:
            require(row.get(field + '_source_sha256') ==
                    scene[field + '_source_sha256'],
                    'source context missing or changed: ' + field)
        require(row.get('vehicle_id') == scene['vehicle_id'] and
                row.get('parking_person_id') == scene['parking_person_id'] and
                row.get('official_device_text') == scene['official_device_text'],
                'original participant/device identity changed')
        for key in ('city_vehicle', 'designated', 'posted'):
            require(row.get(key) is getattr(case, key),
                    'original prerequisite changed: ' + key)
        require(point(row.get('vehicle_center_xy')) and
                rectangle(row.get('vehicle_footprint_rect_m')) and
                number(row.get('speed_mps')) and row['speed_mps'] >= 0,
                'original parking motion or footprint missing')
        if i >= scene['park_start_frame']:
            parked.append(row['speed_mps'] <= .1)
            in_space.append(inside(row['vehicle_center_xy'],
                                   scene['governed_space_rect_m']))
            relation = footprint_relation(row['vehicle_footprint_rect_m'],
                                          scene['governed_space_rect_m'])
            footprint_overlaps.append(relation['overlap_area_m2'] > 0)
    require(parked and all(parked), 'vehicle not parked throughout interval')
    require(all(footprint_overlaps) if case.inside_space else not any(footprint_overlaps),
            'governed-space footprint occupancy wrong')
    return {'case_id': case.name, 'parked_frames': len(parked),
            'all_centers_inside_governed_space': all(in_space),
            'all_footprints_overlap_governed_space': all(footprint_overlaps),
            'city_vehicle': case.city_vehicle,
            'official_posting': case.posted,
            'council_designated': case.designated,
            'legal_judgment': None, 'city_vehicle_scope_judgment': None}
