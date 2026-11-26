"""Source-gated official-device lamp probes for NRS 484D.100(1)."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    device_directs: bool
    lamps_on: bool
    context: str


CASES = (
    Case('day_device_lamps_on', True, True, 'day_clear'),
    Case('day_device_lamps_off', True, False, 'day_clear'),
    Case('day_no_device_lamps_off', False, False, 'day_clear'),
    Case('night_device_lamps_on', True, True, 'night'),
    Case('poor_visibility_device_lamps_on', True, True, 'poor_visibility'),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def statutory_context(scene):
    """Keep independent time and visibility triggers as observations only."""
    sunrise = scene.get('sunrise_time_s')
    sunset = scene.get('sunset_time_s')
    clock = scene.get('clock_time_s')
    visible = scene.get('visibility_ahead_m')
    require(all(number(value) for value in (sunrise, sunset, clock, visible)) and
            0 <= sunrise < sunset < 86400 and 0 <= clock < 86400 and visible >= 0,
            'source-bound statutory context missing')
    return {'half_hour_night': clock >= sunset + 1800 or clock <= sunrise - 1800,
            'under_1000ft_discernibility': visible < 304.8,
            'sunrise_boundary_s': sunrise - 1800,
            'sunset_boundary_s': sunset + 1800,
            'visibility_boundary_m': 304.8}


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact lamp case')
    require(scene.get('cell_id') == 'C230294' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('nevada_jurisdiction') is True and
            scene.get('public_highway') is True and
            scene.get('vehicle_class') == 'ordinary_motor_vehicle' and
            scene.get('parked') is False, 'qualifying highway vehicle missing')
    require(scene.get('device_directs') is case.device_directs and
            scene.get('lamps_on_request') is case.lamps_on and
            scene.get('context') == case.context, 'case variables changed')
    for field in ('jurisdiction', 'highway', 'vehicle_class', 'parking_status',
                  'required_lamp_provisions', 'device_authority',
                  'device_geometry', 'device_message', 'device_timing',
                  'route', 'sunset_sunrise', 'clock', 'visibility'):
        require(scene.get(field + '_source_sha256'),
                'original context missing: ' + field)
    if case.device_directs:
        authority = scene.get('device_authority')
        require(isinstance(authority, dict) and
                authority.get('public_authority_placed') is True and
                authority.get('nrs_484a_145_qualified') is True and
                authority.get('agency') and authority.get('review_reference'),
                'official device authority source incomplete')
        timing = scene.get('device_timing')
        require(isinstance(timing, dict) and timing.get('operative') is True and
                number(timing.get('start_time_s')) and
                number(timing.get('end_time_s')) and
                timing['start_time_s'] <= scene.get('clock_time_s', -1) <= timing['end_time_s'],
                'official device operative timing source incomplete')
        require(scene.get('official_device') is True and
                scene.get('device_message') == 'use_lamps' and
                scene.get('device_operative') is True and
                scene.get('device_governs_route') is True,
                'operative official lamp direction missing')
    else:
        require(scene.get('official_device') is False and
                scene.get('device_operative') is False and
                scene.get('device_governs_route') is False and
                scene.get('device_message') == 'no_device',
                'no-device comparison control changed')
    required = scene.get('required_lamp_ids')
    require(isinstance(required, list) and required and
            all(isinstance(x, str) and x for x in required) and
            len(set(required)) == len(required),
            'class-specific lamp inventory missing')
    provisions = scene.get('required_lamp_provisions')
    require(isinstance(provisions, dict) and set(provisions) == set(required) and
            all(isinstance(citation, str) and citation for citation in provisions.values()),
            'class-specific lamp provision citations missing')
    highway = scene.get('highway')
    require(isinstance(highway, dict) and
            highway.get('public_dedication') is True and
            highway.get('boundaries_documented') is True and
            highway.get('public_vehicular_access') is True,
            'Nevada public highway source incomplete')
    route = scene.get('route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and
                all(number(x) for x in p) for p in route),
            'governed vehicle route missing')
    context = statutory_context(scene)
    if case.context == 'day_clear':
        require(scene['sunrise_time_s'] + 1800 < scene['clock_time_s'] <
                scene['sunset_time_s'] - 1800 and
                scene['visibility_ahead_m'] >= 304.8,
                'isolated daylight device context missing')
    if case.context == 'night':
        require(context['half_hour_night'],
                'half-hour-after-sunset context missing')
    if case.context == 'poor_visibility':
        require(scene['visibility_ahead_m'] < 304.8,
                '1,000-foot discernibility context missing')
    return {'case_id': case.name, 'statutory_context': context,
            'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        if case.device_directs:
            device = adapter.place_official_device(scene['device_xy'], 'use_lamps')
            require(device is not None, 'official lamp device placement failed')
            owned.append(device)
        vehicle = adapter.spawn_vehicle(scene['route_xy'][0])
        require(vehicle is not None, 'vehicle spawn failed')
        owned.append(vehicle)
        adapter.set_route(vehicle, scene['route_xy'])
        for lamp_id in scene['required_lamp_ids']:
            adapter.set_lamp(vehicle, lamp_id, case.lamps_on)
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
    vehicle_id = None
    lamp_counts = {lamp_id: 0 for lamp_id in scene['required_lamp_ids']}
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('frame', 'vehicle_motion', 'lamp_state',
                      'device_authority', 'device_message', 'device_timing',
                      'sunset_sunrise', 'clock', 'visibility'):
            require(row.get(field + '_source_sha256'),
                    'original measurement source missing: ' + field)
        require(row.get('vehicle_class_source_sha256') ==
                scene['vehicle_class_source_sha256'] and
                row.get('device_directs') is case.device_directs and
                row.get('context') == case.context,
                'original vehicle/device context changed')
        require(row.get('vehicle_id'), 'vehicle identity missing')
        vehicle_id = vehicle_id or row['vehicle_id']
        require(row['vehicle_id'] == vehicle_id and
                number(row.get('speed_mps')) and row['speed_mps'] > 0,
                'moving vehicle identity/motion missing')
        states = row.get('lamp_states')
        require(isinstance(states, dict) and
                set(states) == set(lamp_counts) and
                all(type(value) is bool for value in states.values()),
                'actual class-specific lamp states missing')
        for lamp_id, on in states.items():
            lamp_counts[lamp_id] += int(on)
    return {'case_id': case.name, 'frame_count': 900,
            'device_directs': case.device_directs,
            'lamp_on_frame_counts': lamp_counts,
            'statutory_context': statutory_context(scene),
            'legal_judgment': None}


def audit_comparison(reports, cases, changed_fields):
    """Check original measurements and fixed context, without legal labeling."""
    require(len(reports) == len(cases) and len(cases) >= 2,
            'comparison members missing')
    fixed = ('map_sha256', 'vehicle_class_source_sha256', 'route_source_sha256',
             'required_lamp_provisions_source_sha256', 'camera_profile_sha256')
    for report, case in zip(reports, cases):
        require(case in CASES and report.get('case_id') == case.name and
                report.get('frame_count') == 900,
                'comparison original measurement missing')
        require(isinstance(report.get('lamp_on_frame_counts'), dict) and
                report['lamp_on_frame_counts'], 'comparison lamp measurement missing')
        for field in fixed:
            require(report.get(field) and report[field] == reports[0].get(field),
                    'comparison fixed context changed: ' + field)
    allowed = {'device_directs', 'lamps_on', 'context'}
    require(set(changed_fields) <= allowed and changed_fields,
            'comparison difference unknown')
    for field in allowed:
        values = [getattr(case, field) for case in cases]
        if field in changed_fields:
            require(len(set(values)) > 1, 'declared difference absent: ' + field)
        else:
            require(len(set(values)) == 1, 'undeclared difference: ' + field)
    return {'case_ids': [report['case_id'] for report in reports],
            'changed_fields': sorted(changed_fields), 'legal_judgment': None}
