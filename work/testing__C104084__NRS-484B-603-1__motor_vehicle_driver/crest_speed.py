"""Source-bound physical measurements for an approaching hill crest.

These are engineering observations, never a legal threshold for NRS 484B.603(1).
The caller supplies original Native waypoint and frame records; desired speeds
and case names cannot substitute for measured motion.
"""
from __future__ import annotations

import math


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def crest_station(waypoints):
    if not isinstance(waypoints, list) or len(waypoints) < 5:
        raise ValueError('five or more original grade samples required')
    for point in waypoints:
        if not isinstance(point, dict) or not all(_finite(point.get(k)) for k in ('s_m', 'z_m')):
            raise ValueError('finite original station and grade required')
        if not point.get('source_ref'):
            raise ValueError('original grade source required')
    if any(b['s_m'] <= a['s_m'] for a, b in zip(waypoints, waypoints[1:])):
        raise ValueError('original grade stations must increase')
    peak = max(range(len(waypoints)), key=lambda i: waypoints[i]['z_m'])
    if not 0 < peak < len(waypoints) - 1:
        raise ValueError('crest peak must be internal to recorded approach')
    if not (waypoints[peak]['z_m'] > waypoints[0]['z_m'] and
            waypoints[peak]['z_m'] > waypoints[-1]['z_m']):
        raise ValueError('recorded grade has no crest')
    return waypoints[peak]['s_m']


def measure(waypoints, frames, *, approach_start_m):
    """Measure original approach speed change and body clearance.

    No prescribed speed or required deceleration magnitude is inferred.
    A frame is retained only when source references cover both bodies and the
    measured ego speed/position at the same original frame ID.
    """
    crest_s = crest_station(waypoints)
    if not _finite(approach_start_m) or approach_start_m >= crest_s:
        raise ValueError('approach start must precede measured crest')
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError('original frame history required')
    for frame in frames:
        if not isinstance(frame, dict) or not all(_finite(frame.get(k)) for k in
            ('time_s', 'ego_s_m', 'ego_speed_mps', 'other_s_m', 'body_clearance_m')):
            raise ValueError('finite original speed, positions and clearance required')
        if not frame.get('source_ref') or frame.get('frame_id') is None:
            raise ValueError('original frame identity and source required')
        if frame['ego_speed_mps'] < 0 or frame['body_clearance_m'] < 0:
            raise ValueError('negative physical speed or clearance')
    if any(b['time_s'] <= a['time_s'] or b['frame_id'] <= a['frame_id']
           for a, b in zip(frames, frames[1:])):
        raise ValueError('original frame time and identity must increase')
    approach = [f for f in frames if approach_start_m <= f['ego_s_m'] < crest_s]
    if len(approach) < 2:
        raise ValueError('at least two pre-crest original motion samples required')
    if any(b['ego_s_m'] < a['ego_s_m'] for a, b in zip(approach, approach[1:])):
        raise ValueError('ego moved backwards in approach window')
    start, end = approach[0], approach[-1]
    minimum_clearance = min(frames, key=lambda f: f['body_clearance_m'])
    first_decrease = next((f for a, f in zip(approach, approach[1:])
                           if f['ego_speed_mps'] < a['ego_speed_mps']), None)
    return {
        'crest_station_m': crest_s,
        'approach_start_m': approach_start_m,
        'approach_frame_ids': [f['frame_id'] for f in approach],
        'initial_speed_mps': start['ego_speed_mps'],
        'last_precrest_speed_mps': end['ego_speed_mps'],
        'speed_change_mps': end['ego_speed_mps'] - start['ego_speed_mps'],
        'first_speed_decrease_frame_id': first_decrease['frame_id'] if first_decrease else None,
        'first_speed_decrease_station_m': first_decrease['ego_s_m'] if first_decrease else None,
        'minimum_body_clearance_m': minimum_clearance['body_clearance_m'],
        'minimum_clearance_frame_id': minimum_clearance['frame_id'],
        'source_frame_refs': [f['source_ref'] for f in frames],
        'grade_source_refs': [p['source_ref'] for p in waypoints],
        'interpretation_limit': 'Physical context only; necessary decrease, lawful entry and due care require independent legal/context review.'
    }
