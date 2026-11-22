"""Feedback policy for an attempted pass using the opposing lane.

Actual crossing, return, traffic safety and legal status require source review.
"""
from truck_construction import _position, _projected_half_length
from truck_follow_controller import command


class PassingPolicy:
    def __init__(self):
        self.phase = 'approach'

    def update(self, ego, lead):
        ego_front = _position(ego, (1, 0))+_projected_half_length(ego, (1, 0))
        ego_rear = _position(ego, (1, 0))-_projected_half_length(ego, (1, 0))
        lead_front = _position(lead, (1, 0))+_projected_half_length(lead, (1, 0))
        lead_rear = _position(lead, (1, 0))-_projected_half_length(lead, (1, 0))
        if self.phase == 'approach' and lead_rear-ego_front <= 120:
            self.phase = 'passing'
        if self.phase == 'passing' and ego_rear-lead_front >= 15:
            self.phase = 'return'
        return self.phase

    def apply(self, ego, lead, control_factory):
        phase = self.update(ego, lead)
        lane_y = 1.9 if phase == 'passing' else -1.9
        outputs = {}
        for role, actor, target_speed, center in (
                ('ego', ego, 20.0, lane_y), ('lead', lead, 8.0, -1.9)):
            values = command(actor, target_speed_mps=target_speed, lane_center_y_m=center)
            actor.apply_control(control_factory(throttle=values['throttle'],
                                                brake=values['brake'], steer=values['steer']))
            outputs[role] = values
        outputs['phase'] = phase
        return outputs
