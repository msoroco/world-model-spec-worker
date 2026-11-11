"""Engineering counterfactual for a subject that proceeds before opposing clearance.

This policy creates a movement contrast. It does not decide legal fault or set an
immediate-hazard threshold. Original telemetry must establish the realized order.
"""
import math


class ProceedBeforeClearanceController:
    def __init__(self, *, approach_speed_mps=5.0, turn_distance_m=4.0):
        if not all(type(v) in (int, float) and math.isfinite(v) and v > 0
                   for v in (approach_speed_mps, turn_distance_m)):
            raise ValueError('Positive finite proceed-policy tuning required')
        self.approach_speed_mps = approach_speed_mps
        self.turn_distance_m = turn_distance_m
        self.state = 'approach'

    def step(self, *, distance_to_hold_m, ego_speed_mps,
             oncoming_distance_to_conflict_m, oncoming_closing_speed_mps,
             oncoming_in_intersection, oncoming_cleared, turn_complete):
        values = (distance_to_hold_m, ego_speed_mps,
                  oncoming_distance_to_conflict_m, oncoming_closing_speed_mps)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError('Finite measured control inputs required')
        if type(oncoming_in_intersection) is not bool or type(oncoming_cleared) is not bool:
            raise ValueError('Measured opposing state required')
        if type(turn_complete) is not bool:
            raise ValueError('Measured completion state required')
        if turn_complete or self.state == 'complete':
            self.state = 'complete'
            return {'state': 'complete', 'throttle': 0.0, 'brake': 1.0,
                    'steer': 0.0, 'left_indicator': False}
        if distance_to_hold_m <= self.turn_distance_m:
            self.state = 'turn'
        if self.state == 'turn':
            return {'state': 'turn', 'throttle': 0.35, 'brake': 0.0,
                    'steer': -0.45, 'left_indicator': True}
        error = self.approach_speed_mps - ego_speed_mps
        return {'state': 'approach', 'throttle': max(0.0, min(0.5, 0.12 * error)),
                'brake': 0.0, 'steer': 0.0, 'left_indicator': True}
