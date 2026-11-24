"""Source-gated designated-zone flagger probes for NRS 484B.330(1)."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    designated: bool
    authorized: bool
    signal: str
    response: str


CASES = (
    Case('designated_stop_driver_continues', True, True, 'stop', 'continue'),
    Case('designated_stop_driver_stops', True, True, 'stop', 'stop'),
    Case('undesignated_stop_driver_continues', False, True, 'stop', 'continue'),
    Case('unauthorized_stop_driver_continues', True, False, 'stop', 'continue'),
    Case('designated_proceed_driver_continues', True, True, 'proceed', 'continue'),
)


SOURCES = ('driver_identity', 'vehicle_class', 'autonomous_operation',
           'highway_status', 'zone_designation', 'zone_boundaries',
           'flagger_identity', 'flagger_authorization', 'traffic_control_role',
           'signal_content', 'signal_orientation', 'signal_visibility',
           'intended_recipient', 'release_event', 'vehicle_motion')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(v):
    return type(v) in (int, float) and isfinite(v)


def point(v):
    return isinstance(v, (tuple, list)) and len(v) == 2 and all(number(x) for x in v)


def rect(v):
    return (isinstance(v, (tuple, list)) and len(v) == 4 and
            all(number(x) for x in v) and v[0] < v[2] and v[1] < v[3])


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact flagger case')
    require(scene.get('cell_id') == 'C230235' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('qualifying_vehicle') is True and
            scene.get('highway') is True and scene.get('driver_id') and
            scene.get('vehicle_id') and scene.get('flagger_id'),
            'driver/vehicle/highway/flagger identity missing')
    for key in ('designated', 'authorized', 'signal', 'response'):
        require(scene.get(key) == getattr(case, key),
                'case dimension changed: ' + key)
    for field in SOURCES:
        require(scene.get(field + '_source_sha256'),
                'independent source missing: ' + field)
    require(rect(scene.get('zone_rect_m')) and
            point(scene.get('stop_line_xy')) and
            point(scene.get('flagger_xy')),
            'zone/signal geometry missing')
    route = scene.get('vehicle_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(point(p) for p in route), 'vehicle route missing')
    require(type(scene.get('signal_frame')) is int and
            0 <= scene['signal_frame'] < 900 and
            type(scene.get('release_frame')) is int and
            scene['signal_frame'] < scene['release_frame'] < 900,
            'signal/release interval missing')
    return {'case_id': case.name, 'failure_or_refusal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        flagger = adapter.spawn_flagger(scene['flagger_xy'])
        require(flagger is not None, 'flagger spawn failed')
        owned.append(flagger)
        vehicle = adapter.spawn_vehicle(scene['vehicle_route_xy'][0])
        require(vehicle is not None, 'vehicle spawn failed')
        owned.append(vehicle)
        adapter.set_signal(flagger, case.signal, scene['signal_frame'],
                           scene['release_frame'])
        adapter.set_route(vehicle, scene['vehicle_route_xy'], case.response)
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
    active_speeds = []
    active_positions = []
    for i, row in enumerate(rows):
        frame = first + i
        require(row.get('original_frame') == frame and
                number(row.get('time_s')) and
                abs(row['time_s'] - t0 - i / 20) <= .005,
                'original frame/time join invalid')
        for field in SOURCES:
            require(row.get(field + '_source_sha256') ==
                    scene[field + '_source_sha256'],
                    'original source changed: ' + field)
        for field in ('driver_id', 'vehicle_id', 'flagger_id'):
            require(row.get(field) == scene[field],
                    'original participant identity changed: ' + field)
        require(row.get('designated') is case.designated and
                row.get('authorized') is case.authorized and
                row.get('signal') == case.signal and
                row.get('signal_visible') is True and
                row.get('intended_vehicle_id') == scene['vehicle_id'],
                'original signal governance changed')
        require(number(row.get('vehicle_speed_mps')) and
                row['vehicle_speed_mps'] >= 0 and
                point(row.get('vehicle_xy')),
                'original vehicle motion missing')
        if scene['signal_frame'] <= frame < scene['release_frame']:
            active_speeds.append(row['vehicle_speed_mps'])
            active_positions.append(row['vehicle_xy'])
    require(active_speeds, 'active signal interval absent')
    if case.response == 'stop':
        require(all(speed <= .1 for speed in active_speeds),
                'stop response not physically realized')
    else:
        require(any(speed > .5 for speed in active_speeds),
                'continue response not physically realized')
    return {'case_id': case.name, 'active_signal_frames': len(active_speeds),
            'maximum_active_speed_mps': max(active_speeds),
            'first_active_vehicle_xy': active_positions[0],
            'failure_or_refusal_judgment': None}
