"""Assess observed crest passage from original station and frame samples.

This is an engineering event check. It does not establish sight, due care,
collision avoidance, or the legally necessary amount of slowing.
"""
from __future__ import annotations

import math

from crest_speed import crest_station


def assess(waypoints, frames, *, approach_start_m):
    crest_s = crest_station(waypoints)
    if type(approach_start_m) not in (int, float) or not math.isfinite(approach_start_m):
        raise ValueError('finite approach start required')
    if approach_start_m >= crest_s:
        raise ValueError('approach must start before original crest')
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError('original motion frames required')
    previous = None
    approached = None
    crossing = None
    postcrest = None
    for frame in frames:
        if not isinstance(frame, dict) or type(frame.get('frame_id')) is not int:
            raise ValueError('original frame identity required')
        station = frame.get('ego_s_m')
        time = frame.get('time_s')
        if not all(type(value) in (int, float) and math.isfinite(value)
                   for value in (station, time)) or not frame.get('source_ref'):
            raise ValueError('source-bound finite original station and time required')
        if previous is not None:
            if frame['frame_id'] <= previous['frame_id'] or time <= previous['time_s']:
                raise ValueError('original frame order differs')
            if station < previous['ego_s_m']:
                raise ValueError('original ego station reversed')
        if approached is None and approach_start_m <= station < crest_s:
            approached = frame
        if approached is not None and crossing is None and station >= crest_s:
            crossing = frame
        elif crossing is not None and postcrest is None and station > crest_s:
            postcrest = frame
        previous = frame
    if approached is None or crossing is None or postcrest is None:
        raise ValueError('original approach, crest crossing and postcrest samples required')
    return {
        'crest_station_m': crest_s,
        'first_approach_frame_id': approached['frame_id'],
        'crossing_frame_id': crossing['frame_id'],
        'crossing_time_s': crossing['time_s'],
        'crossing_station_m': crossing['ego_s_m'],
        'first_postcrest_frame_id': postcrest['frame_id'],
        'source_refs': [approached['source_ref'], crossing['source_ref'],
                        postcrest['source_ref']],
        'interpretation_limit': 'Observed station passage only; physical visibility, collision avoidance and legal duty remain unjudged.',
    }
