"""Source-bound physical probes for NRS 484B.473(2)."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    lamp_mode: str
    auxiliary_lamp: str
    night: bool
    lawful_park: bool


CASES = (
    Case('night_undimmed_no_aux', 'undimmed', 'none', True, True),
    Case('night_dimmed_no_aux', 'dimmed', 'none', True, True),
    Case('night_undimmed_cowl', 'undimmed', 'cowl', True, True),
    Case('night_undimmed_parking', 'undimmed', 'parking', True, True),
    Case('day_undimmed_no_aux', 'undimmed', 'none', False, True),
    Case('unlawful_park_undimmed', 'undimmed', 'none', True, False),
)

SCENE_SOURCES = ('vehicle_identity', 'highway', 'parking_lawfulness',
                 'nighttime', 'displayed_lights', 'beam_aim', 'cowl_lamp',
                 'parking_lamp', 'curb_geometry', 'standing_purpose',
                 'loading', 'traffic_direction', 'safety_zone',
                 'double_parking', 'grade', 'frame', 'vehicle_motion')
ROW_SOURCES = ('frame', 'vehicle_identity', 'vehicle_motion',
               'parking_lawfulness', 'nighttime', 'displayed_lights',
               'beam_aim', 'cowl_lamp', 'parking_lamp')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def valid_number(value):
    return type(value) in (int, float) and isfinite(value)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact law case')
    require(scene.get('cell_id') == 'C229398' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('qualifying_vehicle') is True and
            scene.get('highway') is True and scene.get('vehicle_id'),
            'vehicle/highway identity missing')
    require(scene.get('night') is case.night and
            scene.get('lawful_park') is case.lawful_park and
            scene.get('lamp_mode') == case.lamp_mode and
            scene.get('auxiliary_lamp') == case.auxiliary_lamp,
            'case dimensions changed')
    for field in SCENE_SOURCES:
        require(scene.get(field + '_source_sha256'),
                'source missing: ' + field)
    route = scene.get('parking_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, (list, tuple)) and len(p) == 2 and
                all(valid_number(v) for v in p) for p in route),
            'parking route geometry missing')
    require(valid_number(scene.get('curb_distance_m')) and
            scene['curb_distance_m'] >= 0 and
            valid_number(scene.get('vehicle_width_m')) and
            scene['vehicle_width_m'] > 0,
            'curb/vehicle geometry missing')
    require(type(scene.get('park_start_frame')) is int and
            scene['park_start_frame'] >= 0, 'parking timing missing')
    return {'case_id': case.name, 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    actor = adapter.spawn_vehicle(scene['parking_route_xy'][0])
    require(actor is not None, 'vehicle spawn failed')
    try:
        adapter.set_parking_route(actor, scene['parking_route_xy'],
                                  scene['park_start_frame'])
        adapter.set_displayed_lamps(actor, case.lamp_mode)
        adapter.set_auxiliary_lamps(actor, case.auxiliary_lamp)
        return {'owned': (actor,), **context}
    except Exception:
        adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    first = rows[0].get('original_frame')
    t0 = rows[0].get('time_s')
    require(type(first) is int and valid_number(t0),
            'original time/frame identity missing')
    stationary = []
    dimmed = []
    identity = None
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                valid_number(row.get('time_s')) and
                abs(row['time_s'] - t0 - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ROW_SOURCES:
            require(row.get(field + '_source_sha256') ==
                    scene[field + '_source_sha256'],
                    'original measurement source changed: ' + field)
        identity = identity or row.get('vehicle_id')
        require(identity == row.get('vehicle_id') == scene['vehicle_id'],
                'original vehicle identity changed')
        require(row.get('night') is case.night and
                row.get('lawful_park') is case.lawful_park and
                row.get('lamp_mode') == case.lamp_mode and
                row.get('auxiliary_lamp') == case.auxiliary_lamp,
                'original law case state changed')
        require(valid_number(row.get('speed_mps')) and
                row['speed_mps'] >= 0 and
                valid_number(row.get('beam_aim_deg')),
                'physical speed/beam measurement missing')
        if i >= scene['park_start_frame']:
            stationary.append(row['speed_mps'] <= .1)
            dimmed.append(row['lamp_mode'] == 'dimmed')
    require(stationary and all(stationary),
            'vehicle not physically parked for original interval')
    return {'case_id': case.name, 'parked_frames': len(stationary),
            'displayed_lamp_mode': case.lamp_mode,
            'auxiliary_lamp': case.auxiliary_lamp,
            'beam_aim_deg_last': rows[-1]['beam_aim_deg'],
            'all_parked_frames_dimmed': all(dimmed),
            'legal_judgment': None}
