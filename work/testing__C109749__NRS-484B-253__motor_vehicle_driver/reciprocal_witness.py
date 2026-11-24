"""Measure the separate later opposing actor in NRS 484B.253 reciprocal cases.

This checks original three-actor event order. Braking is an engineering contrast,
not a legal conclusion that any driver yielded the right-of-way.
"""
from __future__ import annotations

import math

from left_turn_measurements import body_occupancy, opposing_approach


def measure_later_opponent(rows: list[dict], polygon: list,
                           *, expected_braking: bool) -> dict:
    if type(expected_braking) is not bool:
        raise ValueError('exact reciprocal response policy required')
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError('original three-actor frame history required')
    actor_ids = None
    previous_frame = None
    previous_time = None
    observations = []
    for row in rows:
        frame = row.get('frame')
        time = row.get('time_s')
        ids = tuple(row.get(key) for key in ('ego_actor_id', 'opponent_actor_id',
                                             'later_opponent_actor_id'))
        if any(type(actor) is not int for actor in ids) or len(set(ids)) != 3:
            raise ValueError('three distinct original actor identities required')
        if actor_ids is None:
            actor_ids = ids
        elif ids != actor_ids:
            raise ValueError('original later-opponent actor identity drift')
        if (type(frame) is not int or type(time) not in (int, float) or
                not math.isfinite(time) or
                (previous_frame is not None and
                 (frame != previous_frame + 1 or abs(time - previous_time - 0.05) > 0.002))):
            raise ValueError('original 20 Hz frame join required')
        previous_frame, previous_time = frame, time
        if (not row.get('later_opponent_driver_control_source') or
                type(row.get('later_opponent_braking')) is not bool):
            raise ValueError('original later-opponent control readback required')
        speed = row.get('later_opponent_speed_mps')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('original later-opponent speed required')
        later = body_occupancy(row.get('later_opponent_vertices'), polygon)
        initial = body_occupancy(row.get('opponent_vertices'), polygon)
        opposite = opposing_approach(row.get('ego_heading'),
                                     row.get('later_opponent_heading'))
        if opposite > -0.5:
            raise ValueError('later vehicle is not opposite-direction traffic')
        observations.append({'frame': frame, 'initial_clear': not initial['any_vertex_inside'],
                             'ego_committed': row.get('ego_turn_committed') is True,
                             'later_inside': later['any_vertex_inside'],
                             'later_braking': row['later_opponent_braking'],
                             'later_speed_mps': speed})
    first_clear = next((i for i, item in enumerate(observations)
                        if item['initial_clear']), None)
    first_commit = next((i for i, item in enumerate(observations)
                         if item['ego_committed']), None)
    first_later = next((i for i, item in enumerate(observations)
                        if item['later_inside']), None)
    if (observations[0]['initial_clear'] or
            observations[0]['later_inside'] or
            first_clear is None or first_commit is None or first_later is None or
            not first_clear < first_commit <= first_later):
        raise ValueError('initial clearance, ego commitment and later approach order missing')
    response = observations[first_commit:first_later + 1]
    observed_braking = any(item['later_braking'] for item in response)
    if observed_braking != expected_braking:
        raise ValueError('later-opponent measured response differs from exact case')
    return {'later_opponent_actor_id': actor_ids[2],
            'initial_clear_frame': observations[first_clear]['frame'],
            'ego_commit_frame': observations[first_commit]['frame'],
            'later_intersection_frame': observations[first_later]['frame'],
            'later_braking_during_conflict': observed_braking,
            'later_speed_mps_by_frame': [[item['frame'], item['later_speed_mps']]
                                         for item in observations],
            'source': 'original_three_actor_trace_and_control_readback',
            'legal_right_of_way': 'unresolved'}
