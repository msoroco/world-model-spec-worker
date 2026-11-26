"""Source-bound school crossing-zone reversal probes."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from school_timing import derive as derive_timing


@dataclass(frozen=True)
class Case:
    name: str
    children_present: bool
    school_session: bool
    operation_window: bool
    beacon_operational: bool
    beacon_flashing: bool
    sign_limit_active: bool


CASES = (
    Case('children_active_zone', True, True, True, True, True, True),
    Case('no_children', False, True, True, True, True, True),
    Case('school_not_in_session', True, False, False, True, True, True),
    Case('outside_operation_half_hour', True, True, False, True, True, True),
    Case('beacon_class_no_flash', True, True, True, True, False, True),
    Case('sign_limit_inactive', True, True, True, False, False, False),
)


SOURCES = ('driver_identity', 'vehicle_class', 'highway_status',
           'crossing_zone_designation', 'crossing_zone_extent',
           'school_property_nonadjacency', 'designated_pupil_route',
           'children_identity', 'children_location', 'school_calendar',
           'school_operation_time', 'class_hours', 'local_clock',
           'beacon_configuration', 'beacon_state', 'sign_instruction',
           'vehicle_trajectory', 'vehicle_heading', 'travel_direction')


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


def inside(p, box):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact school-zone case')
    require(scene.get('cell_id') == 'C255863' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('qualifying_vehicle') is True and
            scene.get('highway') is True and
            scene.get('driver_id') and scene.get('vehicle_id'),
            'driver/vehicle/highway missing')
    for name in ('children_present', 'school_session', 'operation_window',
                 'beacon_operational', 'beacon_flashing', 'sign_limit_active'):
        require(scene.get(name) is getattr(case, name),
                'case condition changed: ' + name)
    timing = scene.get('timing_packet')
    facts = derive_timing(timing)
    require(timing['local_datetime'] == scene.get('local_datetime'),
            'local clock and timing source differ')
    for name in ('school_session', 'operation_window', 'beacon_operational',
                 'beacon_flashing', 'sign_limit_active'):
        require(facts[name] is getattr(case, name),
                'independent timing/device readback differs: ' + name)
    if case.name == 'beacon_class_no_flash':
        require(facts['during_class'] is True,
                'beacon exception requires independent class hours')
    for name in SOURCES:
        digest = scene.get(name + '_source_sha256')
        require(isinstance(digest, str) and len(digest) == 64 and
                all(c in '0123456789abcdef' for c in digest),
                'independent source missing: ' + name)
    require(rect(scene.get('crossing_zone_rect_m')) and
            rect(scene.get('school_property_rect_m')) and
            scene.get('nonadjacent_street') is True and
            scene.get('pupil_route_designated') is True,
            'crossing-zone definition context missing')
    route = scene.get('reversal_route_xy')
    require(isinstance(route, list) and len(route) >= 3 and
            all(point(p) for p in route), 'physical reversal route missing')
    require(type(scene.get('turn_start_frame')) is int and
            type(scene.get('turn_end_frame')) is int and
            0 <= scene['turn_start_frame'] < scene['turn_end_frame'] < 900,
            'reversal interval missing')
    require(scene.get('local_datetime') and
            scene.get('school_calendar_ref') and
            scene.get('operation_schedule_ref'),
            'independent local time/calendar missing')
    children = scene.get('children')
    require(isinstance(children, list) and
            all(isinstance(x, dict) and x.get('id') and point(x.get('xy'))
                for x in children) and
            len({x['id'] for x in children}) == len(children),
            'children identities/locations missing')
    require(any(inside(x['xy'], scene['crossing_zone_rect_m'])
                for x in children) is case.children_present,
            'children case position missing')
    return {'case_id': case.name, 'uturn_legal_judgment': None,
            'children_presence_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        vehicle = adapter.spawn_vehicle(scene['reversal_route_xy'][0])
        require(vehicle is not None, 'vehicle spawn failed')
        owned.append(vehicle)
        for child in scene['children']:
            actor = adapter.spawn_child(child['id'], child['xy'])
            require(actor is not None, 'child spawn failed')
            owned.append(actor)
        adapter.set_reversal_route(vehicle, scene['reversal_route_xy'],
                                   scene['turn_start_frame'],
                                   scene['turn_end_frame'])
        adapter.set_beacon(case.beacon_operational,
                           case.beacon_flashing)
        device = adapter.read_beacon()
        require(isinstance(device, dict) and
                device.get('operational') is case.beacon_operational and
                device.get('flashing') is case.beacon_flashing,
                'Native beacon readback differs from reviewed case')
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
    require(type(first) is int and number(t0),
            'original frame/time missing')
    headings = []
    directions = []
    for i, row in enumerate(rows):
        frame = first + i
        require(row.get('original_frame') == frame and
                number(row.get('time_s')) and
                abs(row['time_s'] - t0 - i / 20) <= .005,
                'original frame/time join invalid')
        for name in SOURCES:
            require(row.get(name + '_source_sha256') ==
                    scene[name + '_source_sha256'],
                    'original source changed: ' + name)
        require(row.get('driver_id') == scene['driver_id'] and
                row.get('vehicle_id') == scene['vehicle_id'],
                'driver/vehicle identity changed')
        for name in ('children_present', 'school_session',
                     'operation_window', 'beacon_operational',
                     'beacon_flashing', 'sign_limit_active'):
            require(row.get(name) is getattr(case, name),
                    'original exception state changed: ' + name)
        require(point(row.get('vehicle_xy')) and
                number(row.get('vehicle_heading_deg')) and
                row.get('travel_direction') in ('forward', 'reverse'),
                'original reversal motion missing')
        children = row.get('children_xy')
        require(isinstance(children, dict) and
                set(children) == {x['id'] for x in scene['children']} and
                all(point(p) for p in children.values()),
                'children identity/location missing')
        observed = any(inside(p, scene['crossing_zone_rect_m'])
                       for p in children.values())
        require(observed is case.children_present,
                'physical children-location case changed')
        if scene['turn_start_frame'] <= i <= scene['turn_end_frame']:
            require(inside(row['vehicle_xy'], scene['crossing_zone_rect_m']),
                    'turn left crossing zone')
            headings.append(row['vehicle_heading_deg'])
            directions.append(row['travel_direction'])
    require(headings and max(headings) - min(headings) >= 150,
            'planned physical reversal not realized')
    return {'case_id': case.name, 'turn_frames': len(headings),
            'heading_span_deg': max(headings) - min(headings),
            'travel_directions': sorted(set(directions)),
            'uturn_legal_judgment': None,
            'children_presence_judgment': None}
