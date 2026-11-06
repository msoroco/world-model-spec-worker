"""One requested driver response policy for both curb-entry probes.

This only schedules controls. Native speed, stopping distance and yield are
measured later from retained actor state; CPU checks never claim realization.
"""


class BrakingPolicy:
    def __init__(self, reaction_s=0.8, speed_threshold_mps=0.2):
        if reaction_s <= 0 or speed_threshold_mps <= 0:
            raise ValueError('Driver policy thresholds must be positive')
        self.reaction_s = reaction_s
        self.speed_threshold_mps = speed_threshold_mps
        self.departure_observed_s = None
        self.brake_command_onset_s = None

    def command(self, time_s):
        if time_s < 0:
            raise ValueError('Driver policy time must be nonnegative')
        if self.departure_observed_s is None or time_s + 1e-9 < self.departure_observed_s + self.reaction_s:
            return 'hold_approach_speed'
        if self.brake_command_onset_s is None:
            self.brake_command_onset_s = time_s
        return 'full_brake'

    def observe(self, time_s, pedestrian_speed_mps):
        if time_s < 0 or pedestrian_speed_mps < 0:
            raise ValueError('Driver policy observation invalid')
        if self.departure_observed_s is None and pedestrian_speed_mps > self.speed_threshold_mps:
            self.departure_observed_s = time_s
        return self.departure_observed_s


def cpu_probe(departure_s, rate_hz=20):
    policy = BrakingPolicy()
    states = []
    for frame in range(240):
        time_s = frame/rate_hz
        states.append(policy.command(time_s))
        policy.observe(time_s, 3 if time_s >= departure_s else 0)
    return {'departure_observed_s': policy.departure_observed_s,
            'brake_command_onset_s': policy.brake_command_onset_s,
            'brake_command_count': states.count('full_brake'),
            'policy': 'pedestrian-speed-triggered 0.8 s reaction then full brake',
            'physical_braking_measured': False}
