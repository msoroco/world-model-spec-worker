"""Source-gated control requests for the C153046 red-left comparison attempts.

Commands are requests to a Native adapter. Only original traces can establish
whether a stop, extreme-left position or yield was physically realized.
"""
from __future__ import annotations

import math


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('observed ' + name + ' missing')
    return float(value)


class RedLeftController:
    def __init__(self, case_id: str, variables: dict, site: dict,
                 approach_hold_margin_m: float = 1.0,
                 yield_release_delay_s: float = 0.0):
        self.case_id = case_id
        self.variables = variables
        self.site = site
        if variables.get('signal_request') != 'steady_red_alone':
            raise ValueError('case signal request unsupported')
        if variables.get('stop_request') not in ('complete_stop', 'rolling'):
            raise ValueError('case stop request unsupported')
        if variables.get('approach_position') not in ('extreme_left', 'inner_lane'):
            raise ValueError('case approach position unsupported')
        if variables.get('receiving_direction') not in ('one_way_left', 'two_way'):
            raise ValueError('case receiving direction unsupported')
        if variables.get('conflict_response_request') not in (
            'no_conflict', 'pedestrian_yield', 'pedestrian_advance',
            'traffic_yield', 'traffic_advance'):
            raise ValueError('case conflict request unsupported')
        if not site.get('source_packet_sha256') or not site.get('signal_actor_id'):
            raise ValueError('reviewed site identity missing')
        if not site.get('left_lane_id') or not site.get('inner_lane_id'):
            raise ValueError('reviewed approach lanes missing')
        if site.get('receiving_direction') != variables['receiving_direction']:
            raise ValueError('receiving road differs from exact case')
        self.approach_hold_margin_m = _number(approach_hold_margin_m, 'approach hold margin')
        if not 0.5 <= self.approach_hold_margin_m <= 3.0:
            raise ValueError('approach hold margin outside tested range')
        self.yield_release_delay_s = _number(yield_release_delay_s, 'yield release delay')
        if not 0.0 <= self.yield_release_delay_s <= 2.0:
            raise ValueError('yield release delay outside tested range')
        self.stop_seen = False
        self.last_conflict_time = None
        self.previous_frame = None
        self.previous_time = None

    def step(self, observation: dict) -> dict:
        """Return one adapter request from one original Native observation."""
        if observation.get('origin') != 'native_world_snapshot':
            raise ValueError('original Native observation missing')
        if observation.get('source_packet_sha256') != self.site['source_packet_sha256']:
            raise ValueError('site packet source changed')
        if str(observation.get('signal_actor_id')) != str(self.site['signal_actor_id']):
            raise ValueError('official signal actor changed')
        if observation.get('signal_state') != 'steady_red_alone':
            raise ValueError('red-alone signal observation missing')
        frame = observation.get('frame')
        time_s = _number(observation.get('time_s'), 'time')
        if type(frame) is not int:
            raise ValueError('original frame missing')
        if self.previous_frame is not None and (
            frame != self.previous_frame + 1 or
            abs(time_s - self.previous_time - 0.05) > 0.001
        ):
            raise ValueError('original 20 Hz sequence broken')
        expected_lane = (self.site['left_lane_id'] if
                         self.variables['approach_position'] == 'extreme_left' else
                         self.site['inner_lane_id'])
        if observation.get('ego_lane_id') != expected_lane:
            raise ValueError('actual approach lane differs from case')
        distance = _number(observation.get('body_front_to_stop_m'), 'body-front distance')
        speed = _number(observation.get('speed_m_s'), 'ego speed')
        if speed < 0:
            raise ValueError('negative ego speed')
        participants = observation.get('directed_participants')
        if not isinstance(participants, list):
            raise ValueError('directed participant inventory missing')
        occupied = set()
        for participant in participants:
            if (participant.get('kind') not in ('pedestrian', 'traffic') or
                type(participant.get('conflict_zone_occupied')) is not bool or
                not participant.get('native_actor_id') or
                not participant.get('source_citation')):
                raise ValueError('directed participant source missing')
            if participant['conflict_zone_occupied']:
                occupied.add(participant['kind'])
        policy = self.variables['conflict_response_request']
        target = 'pedestrian' if policy.startswith('pedestrian') else (
            'traffic' if policy.startswith('traffic') else None)
        if target and not any(p['kind'] == target for p in participants):
            raise ValueError('case conflict participant absent')
        if target in occupied:
            self.last_conflict_time = time_s
        self.previous_frame, self.previous_time = frame, time_s
        if distance > self.approach_hold_margin_m:
            action = 'approach_stop_reference'
        elif not self.stop_seen and self.variables['stop_request'] == 'complete_stop':
            action = 'hold_before_reference'
            if speed <= 0.05 and distance >= 0:
                self.stop_seen = True
        elif target in occupied and policy.endswith('yield'):
            action = 'hold_for_directed_conflict'
        elif (target and policy.endswith('yield') and
              self.last_conflict_time is not None and
              time_s - self.last_conflict_time < self.yield_release_delay_s):
            action = 'hold_for_directed_conflict_release'
        else:
            action = 'turn_left_request'
        return {'case_id': self.case_id, 'native_frame': frame, 'action': action,
                'stop_observed': self.stop_seen,
                'conflict_occupied': sorted(occupied),
                'legal_judgment': 'unresolved',
                'physical_acceptance_claimed': False}
