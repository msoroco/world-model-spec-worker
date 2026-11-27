"""Source-gated red-curb activity and exception probes for LVMC 11.52.030(A)."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    vehicle_kind: str
    sign: str
    activity: str
    duration_s: int
    purpose: str
    mail_adjacent: bool = False


CASES = (
    Case('ordinary_park', 'ordinary', 'none', 'park', 60, 'ordinary'),
    Case('ordinary_stop_unattended', 'ordinary', 'none', 'stop', 30, 'ordinary'),
    Case('ordinary_stand', 'ordinary', 'none', 'stand', 45, 'ordinary'),
    Case('ordinary_park_signed', 'ordinary', 'tour_shuttle_limo', 'park', 60, 'ordinary'),
    Case('tour_bus_1799', 'tour_bus', 'tour_shuttle_limo', 'park', 1799, 'passenger_loading'),
    Case('tour_bus_1800', 'tour_bus', 'tour_shuttle_limo', 'park', 1800, 'passenger_loading'),
    Case('tour_bus_1801', 'tour_bus', 'tour_shuttle_limo', 'park', 1801, 'passenger_loading'),
    Case('tour_bus_wrong_sign', 'tour_bus', 'none', 'park', 1800, 'passenger_loading'),
    Case('tour_bus_nonloading', 'tour_bus', 'tour_shuttle_limo', 'park', 1800, 'ordinary'),
    Case('shuttle_bus_1800', 'shuttle_bus', 'tour_shuttle_limo', 'park', 1800, 'passenger_unloading'),
    Case('limo_1800', 'limo', 'tour_shuttle_limo', 'park', 1800, 'passenger_loading'),
    Case('rtc_bus_1800', 'rtc_bus', 'rtc_bus', 'park', 1800, 'passenger_loading'),
    Case('rtc_bus_1799', 'rtc_bus', 'rtc_bus', 'park', 1799, 'passenger_loading'),
    Case('rtc_bus_1801', 'rtc_bus', 'rtc_bus', 'park', 1801, 'passenger_loading'),
    Case('armored_business', 'armored_car', 'none', 'park', 120, 'business'),
    Case('armored_nonbusiness', 'armored_car', 'none', 'park', 120, 'ordinary'),
    Case('emergency_business', 'emergency_vehicle', 'none', 'park', 120, 'business'),
    Case('emergency_nonbusiness', 'emergency_vehicle', 'none', 'park', 120, 'ordinary'),
    Case('mail_stop', 'ordinary', 'none', 'stop', 20, 'mail_deposit', True),
    Case('mail_stop_no_deposit', 'ordinary', 'none', 'stop', 20, 'ordinary', True),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact red-curb case')
    require(scene.get('cell_id') == 'C229452' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('municipal_jurisdiction') is True and
            scene.get('red_curb_paint') is True,
            'jurisdiction or governed red curb missing')
    require(scene.get('vehicle_kind') == case.vehicle_kind and
            scene.get('sign') == case.sign and
            scene.get('activity') == case.activity and
            scene.get('purpose') == case.purpose,
            'case variables changed')
    for field in ('jurisdiction', 'red_curb', 'governed_location',
                  'parking_position', 'vehicle_classification', 'sign',
                  'activity', 'purpose', 'attendance', 'engine',
                  'traffic_conflict', 'police_direction', 'device_direction'):
        require(scene.get(field + '_source_sha256'),
                'original context missing: ' + field)
    if case.vehicle_kind in ('tour_bus', 'shuttle_bus', 'limo', 'rtc_bus',
                             'armored_car', 'emergency_vehicle'):
        require(scene.get('vehicle_status_source_sha256'),
                'special vehicle status source missing')
    require(scene.get('mail_dropbox_adjacent') is case.mail_adjacent,
            'mail dropbox adjacency differs from selected case')
    if case.mail_adjacent:
        require(scene.get('mail_dropbox_adjacent') is True and
                scene.get('mail_dropbox_source_sha256') and
                scene.get('mail_activity_source_sha256'),
                'adjacent U.S. mail box/activity source missing')
    route = scene.get('parking_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and
                all(number(v) for v in p) for p in route),
            'parking route missing')
    return {'case_id': case.name, 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        adapter.mark_red_curb(scene['curb_segment_id'])
        adapter.set_sign(case.sign, scene.get('sign_text'))
        vehicle = adapter.spawn_vehicle(case.vehicle_kind,
                                        scene['parking_route_xy'][0])
        require(vehicle is not None, 'vehicle spawn failed')
        owned.append(vehicle)
        adapter.set_parking_route(vehicle, scene['parking_route_xy'])
        adapter.set_halt_activity(vehicle, case.activity, case.purpose)
        return {'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_activity(events: list[Mapping], scene: Mapping, case: Case):
    """A source-linked long event trace is required for the 30-minute probes."""
    validate_scene(scene, case)
    require(len(events) >= 2, 'original halt event trace missing')
    vehicle_id = events[0].get('vehicle_id')
    require(vehicle_id, 'vehicle identity missing')
    times = []
    for event in events:
        require(event.get('vehicle_id') == vehicle_id and
                event.get('red_curb_source_sha256') ==
                scene['red_curb_source_sha256'] and
                event.get('activity') == case.activity and
                event.get('purpose') == case.purpose,
                'original activity/context changed')
        for field in ('event', 'vehicle_motion', 'curb_position', 'activity',
                      'attendance', 'engine', 'sign', 'purpose'):
            require(event.get(field + '_source_sha256'),
                    'original event source missing: ' + field)
        require(number(event.get('original_time_s')) and
                number(event.get('vehicle_speed_mps')) and
                event['vehicle_speed_mps'] >= 0 and
                event.get('halted') is True,
                'original halt motion/time missing')
        times.append(event['original_time_s'])
    require(all(b > a for a, b in zip(times, times[1:])),
            'original time not increasing')
    duration = times[-1] - times[0]
    require(abs(duration - case.duration_s) <= .001,
            'requested boundary duration not evidenced')
    return {'case_id': case.name, 'original_duration_s': duration,
            'vehicle_kind': case.vehicle_kind, 'activity': case.activity,
            'purpose': case.purpose, 'attended': events[-1].get('attended'),
            'engine_running': events[-1].get('engine_running'),
            'traffic_conflict': scene.get('traffic_conflict'),
            'police_direction': scene.get('police_direction'),
            'device_direction': scene.get('device_direction'),
            'legal_judgment': None}
