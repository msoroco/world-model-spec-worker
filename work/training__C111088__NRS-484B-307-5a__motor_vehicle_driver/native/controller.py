"""Straight-arrow yield controller for the proposed C111088 Native attempt.

The caller must supply same-frame original signal and actor observations. This
module only chooses an action; it does not assert that any capture occurred.
"""
from __future__ import annotations


def choose_action(signal: dict, participants: list[dict], *, frame: int) -> dict:
    if signal.get('frame') != frame or signal.get('faces_ego') is not True:
        raise ValueError('Missing same-frame governing signal observation')
    if signal.get('aspects') != ['green_straight_arrow']:
        raise ValueError('Sole green straight-through arrow not observed')
    for actor in participants:
        if actor.get('frame') != frame or not actor.get('actor_id'):
            raise ValueError('Missing same-frame participant identity')
        if actor.get('kind') not in ('motor_vehicle', 'pedestrian'):
            raise ValueError('Unsupported conflict participant kind')
        if actor.get('lawfully_within') is None or actor.get('within_intersection_or_adjacent_crosswalk') is None:
            raise ValueError('Missing participant right-of-way or location observation')
    conflicts = [actor['actor_id'] for actor in participants
                 if actor['lawfully_within'] and actor['within_intersection_or_adjacent_crosswalk']]
    return {'frame': frame, 'route': 'straight', 'turn_command': 0.0,
            'target_speed_m_s': 0.0 if conflicts else 4.0,
            'brake': 1.0 if conflicts else 0.0,
            'yielding_to_actor_ids': conflicts,
            'basis': 'sole governing straight arrow and same-frame lawful occupancy'}
