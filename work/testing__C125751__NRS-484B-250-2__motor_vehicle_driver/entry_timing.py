"""Measure source-bound crossing entry order and timing without a legal cutoff."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = 'testing__C125751__NRS-484B-250-2__motor_vehicle_driver'
CASES = ('precedence', 'advance', 'timing_below', 'timing_inside', 'timing_above')


def _pair(value, label):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError(f'{label} must be finite xy')
    return value


def _inside(vertices, bounds):
    xs, ys = zip(*vertices)
    return max(xs) >= bounds[0] and min(xs) <= bounds[2] and max(ys) >= bounds[1] and min(ys) <= bounds[3]


def measure(trace, survey):
    case = trace.get('case_id')
    if case not in {ASSIGNMENT + '__' + suffix for suffix in CASES}:
        raise ValueError('foreign exact timing case')
    if survey.get('cell_id') != 'C125751' or survey.get('crossing_kind') != 'median_opening_roadway_crossing':
        raise ValueError('identified roadway crossing source missing')
    bounds = survey.get('crossing_bounds_xy_m')
    if (not isinstance(bounds, list) or len(bounds) != 4 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds) or
            bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        raise ValueError('observed crossing bounds missing')
    if trace.get('map_sha256') != survey.get('opendrive_sha256'):
        raise ValueError('original map source differs')
    roads = survey.get('approach_road_ids')
    if not isinstance(roads, dict) or set(roads) != {'ego', 'other'} or roads['ego'] == roads['other']:
        raise ValueError('different highway approach IDs required')
    if survey.get('public_highway_source') is None:
        raise ValueError('public highway source required')
    if survey.get('governing_device') != 'official_traffic_light':
        raise ValueError('official traffic-light context required')
    ego_direction = _pair(survey.get('ego_direction_xy'), 'ego direction')
    other_origin = _pair(survey.get('other_approach_xy'), 'other approach')
    ego_origin = _pair(survey.get('ego_approach_xy'), 'ego approach')
    vector = [other_origin[i] - ego_origin[i] for i in range(2)]
    cross = ego_direction[0] * vector[1] - ego_direction[1] * vector[0]
    if abs(cross) < 0.01 or math.hypot(*ego_direction) < 0.01:
        raise ValueError('left/right approach geometry ambiguous')
    frames = trace.get('frames')
    if not isinstance(frames, list) or len(frames) != 900:
        raise ValueError('900 original crossing frames required')
    actor_ids = trace.get('actor_ids')
    if not isinstance(actor_ids, dict) or set(actor_ids) != {'ego', 'other'} or actor_ids['ego'] == actor_ids['other']:
        raise ValueError('two distinct original actors required')
    first_frame = first_time = None
    entries = {'ego': None, 'other': None}
    prior_inside = {'ego': False, 'other': False}
    device_states = set()
    for i, row in enumerate(frames):
        native_frame = row.get('native_frame_id')
        native_time = row.get('native_elapsed_seconds')
        if (row.get('frame') != i or not math.isclose(row.get('time_s', -1), i / 20, abs_tol=1e-5) or
                type(native_frame) is not int or type(native_time) not in (int, float) or
                not math.isfinite(native_time)):
            raise ValueError('original frame/time source join missing')
        if first_frame is None:
            first_frame, first_time = native_frame, native_time
        if native_frame != first_frame + i or not math.isclose(native_time - first_time, i / 20, abs_tol=.002):
            raise ValueError('original Native 20 Hz clock discontinuity')
        state = row.get('governing_device_readback')
        if state not in ('red', 'yellow', 'green', 'flashing', 'inoperative'):
            raise ValueError('original governing device readback missing')
        device_states.add(state)
        for name in ('ego', 'other'):
            actor = row.get(name)
            if not isinstance(actor, dict) or actor.get('id') != actor_ids[name] or actor.get('road_id') != roads[name]:
                raise ValueError('original actor or approach road differs')
            vertices = actor.get('body_vertices_xy_m')
            if not isinstance(vertices, list) or len(vertices) < 4:
                raise ValueError('original actor footprint missing')
            vertices = [_pair(point, 'body vertex') for point in vertices]
            inside = _inside(vertices, bounds)
            if i == 0 and inside:
                raise ValueError('entry not observed from outside crossing')
            if inside and not prior_inside[name] and entries[name] is None:
                entries[name] = {'frame': i, 'native_frame_id': native_frame,
                                 'upper_elapsed_seconds': native_time,
                                 'lower_elapsed_seconds': frames[i-1]['native_elapsed_seconds']}
            prior_inside[name] = inside
    if any(value is None for value in entries.values()):
        raise ValueError('both original intersection entries required')
    difference = entries['ego']['upper_elapsed_seconds'] - entries['other']['upper_elapsed_seconds']
    return {'case_id': case, 'entry_brackets': entries,
            'ego_minus_other_upper_entry_s': difference,
            'other_approach_side_of_ego': 'right' if cross < 0 else 'left',
            'governing_device_states': sorted(device_states),
            'approximately_same_time_judgment': 'unresolved',
            'statutory_applicability': 'unresolved_official_device_exclusion_and_subsection_4',
            'right_of_way_judgment': 'unresolved'}


def measure_sealed(root, manifest_path, survey_path):
    root = Path(root).resolve()
    manifest_path, survey_path = Path(manifest_path), Path(survey_path)
    manifest = json.loads(manifest_path.read_text())
    survey = json.loads(survey_path.read_text())
    if manifest.get('survey_sha256') != hashlib.sha256(survey_path.read_bytes()).hexdigest():
        raise ValueError('original surveyed crossing packet hash differs')
    ref = manifest.get('trace')
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
        raise ValueError('original trace reference required')
    relative = Path(ref['path'])
    if relative.is_absolute() or any(part in ('.', '..') for part in relative.parts):
        raise ValueError('original trace path escapes attempt')
    trace_path = (root / relative).resolve()
    if not trace_path.is_relative_to(root) or not trace_path.is_file():
        raise ValueError('original trace missing')
    raw = trace_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get('sha256'):
        raise ValueError('original trace digest differs')
    return measure(json.loads(raw), survey)
