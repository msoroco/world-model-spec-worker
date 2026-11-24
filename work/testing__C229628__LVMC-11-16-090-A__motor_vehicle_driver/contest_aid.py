"""Source-bound aid conduct probes for LVMC 11.16.090(A)."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    cue: bool
    candidate_contest: bool
    highway: bool


CASES = (
    Case('start_cue_candidate_contest', True, True, True),
    Case('no_cue_candidate_contest', False, True, True),
    Case('start_cue_no_contest', True, False, True),
    Case('start_cue_off_highway', True, True, False),
)


SOURCE_FIELDS = ('ego_identity', 'other_identity', 'ego_vehicle',
                 'other_vehicle', 'municipal_jurisdiction', 'highway_status',
                 'lane_marking', 'racing_route', 'contest_episode',
                 'cue_conduct', 'cue_timing', 'other_motion', 'ego_motion',
                 'contest_meaning', 'aid_abet_meaning')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(v):
    return type(v) in (int, float) and isfinite(v)


def point(v):
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(number(x) for x in v)


def route(v):
    return isinstance(v, list) and len(v) >= 2 and all(point(p) for p in v)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact contest-aid case')
    require(scene.get('cell_id') == 'C229628' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('municipal_jurisdiction') is True,
            'cell/actor/jurisdiction missing')
    require(scene.get('highway') is case.highway and
            scene.get('candidate_contest') is case.candidate_contest and
            scene.get('cue') is case.cue, 'case dimensions changed')
    for name in ('ego_person_id', 'other_person_id', 'ego_vehicle_id',
                 'other_vehicle_id'):
        require(scene.get(name), name + ' missing')
    require(scene['ego_person_id'] != scene['other_person_id'] and
            scene['ego_vehicle_id'] != scene['other_vehicle_id'],
            'participants collapsed')
    for name in SOURCE_FIELDS:
        require(scene.get(name + '_source_sha256'),
                'independent source missing: ' + name)
    require(route(scene.get('ego_route_xy')) and
            route(scene.get('other_route_xy')) and
            route(scene.get('lane_marking_xy')),
            'racing route or lane marking missing')
    require(type(scene.get('cue_frame')) is int and
            0 <= scene['cue_frame'] < 900 and
            type(scene.get('other_start_frame')) is int and
            scene['cue_frame'] < scene['other_start_frame'] < 900,
            'assistance timing relation missing')
    return {'case_id': case.name, 'aid_abet_judgment': None,
            'contest_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        ego = adapter.spawn_vehicle(scene['ego_route_xy'][0])
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        other = adapter.spawn_vehicle(scene['other_route_xy'][0])
        require(other is not None, 'other spawn failed')
        owned.append(other)
        adapter.set_route(ego, scene['ego_route_xy'])
        adapter.set_route(other, scene['other_route_xy'])
        adapter.set_start_cue(ego, scene['cue_frame'], case.cue)
        adapter.set_other_start(other, scene['other_start_frame'],
                                case.candidate_contest)
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
            'original frame/time identity missing')
    cue_frames = []
    other_motion_frames = []
    max_ego_speed = max_other_speed = 0.
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - t0 - i / 20) <= .005,
                'original frame/time join invalid')
        for name in SOURCE_FIELDS:
            require(row.get(name + '_source_sha256') ==
                    scene[name + '_source_sha256'],
                    'original source changed: ' + name)
        for name in ('ego_person_id', 'other_person_id', 'ego_vehicle_id',
                     'other_vehicle_id'):
            require(row.get(name) == scene[name],
                    'participant identity changed: ' + name)
        require(row.get('highway') is case.highway and
                row.get('candidate_contest') is case.candidate_contest,
                'original highway/episode context changed')
        for name in ('ego_speed_mps', 'other_speed_mps',
                     'ego_accel_mps2', 'other_accel_mps2'):
            require(number(row.get(name)), 'original motion missing: ' + name)
        for name in ('ego_xy', 'other_xy'):
            require(point(row.get(name)), 'original position missing: ' + name)
        if row.get('cue_observed') is True:
            cue_frames.append(first + i)
        if row['other_speed_mps'] > .5:
            other_motion_frames.append(first + i)
        max_ego_speed = max(max_ego_speed, row['ego_speed_mps'])
        max_other_speed = max(max_other_speed, row['other_speed_mps'])
    require(cue_frames == ([scene['cue_frame']] if case.cue else []),
            'cue realization differs from case')
    require(other_motion_frames and
            min(other_motion_frames) >= scene['other_start_frame'],
            'other participant start missing or early')
    return {'case_id': case.name, 'cue_frame': cue_frames[0] if cue_frames else None,
            'other_motion_first_frame': min(other_motion_frames),
            'max_ego_speed_mps': max_ego_speed,
            'max_other_speed_mps': max_other_speed,
            'aid_abet_judgment': None, 'contest_judgment': None}
