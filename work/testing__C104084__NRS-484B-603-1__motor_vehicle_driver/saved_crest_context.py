"""Check original road, limit, and separate participant context for a crest probe.

These are retained physical and setup facts. They do not decide lawful entry,
due care, or whether the measured decrease was legally necessary.
"""
from __future__ import annotations

import math


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def audit_context(context, other_route, frames, *, grade_source_sha256,
                  approach_start_m, crest_station_m):
    if not isinstance(context, dict) or not isinstance(other_route, list):
        raise ValueError('original highway and other route context required')
    if context.get('map_grade_sha256') != grade_source_sha256:
        raise ValueError('highway context grade source differs')
    if context.get('road_id') != 603 or context.get('highway_status') != 'source_observed_road':
        raise ValueError('original highway road context required')
    if not context.get('highway_source_ref'):
        raise ValueError('original highway source reference required')
    limit = context.get('prescribed_limit_mps')
    if not _finite(limit) or limit <= 0 or not context.get('limit_source_ref'):
        raise ValueError('source-bound prescribed speed limit required')
    if (not _finite(approach_start_m) or not _finite(crest_station_m) or
            approach_start_m >= crest_station_m):
        raise ValueError('source-measured precrest approach window required')
    precrest = [frame for frame in frames
                if approach_start_m <= frame['ego_s_m'] < crest_station_m]
    if len(precrest) < 2 or precrest[0]['ego_speed_mps'] >= limit:
        raise ValueError('measured below-limit precrest approach required')
    ego_id, other_id = context.get('ego_actor_id'), context.get('other_actor_id')
    if not isinstance(ego_id, str) or not isinstance(other_id, str) or not ego_id or not other_id or ego_id == other_id:
        raise ValueError('distinct original participant identities required')
    if context.get('lawful_entry_review') != 'unresolved' or context.get('due_care_review') != 'unresolved':
        raise ValueError('legal entry and due care must remain unresolved')
    if len(other_route) < 5:
        raise ValueError('five original other vehicle route points required')
    stations = []
    for point in other_route:
        if (not isinstance(point, dict) or point.get('road_id') != context['road_id'] or
                point.get('lane_id') != 1 or not _finite(point.get('s_m')) or
                not point.get('source_ref')):
            raise ValueError('original opposing vehicle route source required')
        stations.append(point['s_m'])
    if any(b >= a for a, b in zip(stations, stations[1:])):
        raise ValueError('opposing route stations must decrease')
    prior_other = None
    for frame in frames:
        if (frame.get('ego_actor_id') != ego_id or frame.get('other_actor_id') != other_id or
                not frame.get('other_source_ref')):
            raise ValueError('original frame participant source join differs')
        station = frame['other_s_m']
        if station < stations[-1] or station > stations[0]:
            raise ValueError('other vehicle left original route extent')
        if prior_other is not None and station > prior_other:
            raise ValueError('other vehicle reversed on original opposing route')
        prior_other = station
    return {
        'road_id': context['road_id'], 'highway_source_ref': context['highway_source_ref'],
        'prescribed_limit_mps': limit, 'limit_source_ref': context['limit_source_ref'],
        'first_approach_speed_mps': precrest[0]['ego_speed_mps'],
        'first_approach_frame_id': precrest[0]['frame_id'],
        'below_limit_at_first_approach': True,
        'ego_actor_id': ego_id, 'other_actor_id': other_id,
        'other_route_point_count': len(stations),
        'lawful_entry_review': 'unresolved', 'due_care_review': 'unresolved',
        'legal_verdict_claimed': False,
    }
