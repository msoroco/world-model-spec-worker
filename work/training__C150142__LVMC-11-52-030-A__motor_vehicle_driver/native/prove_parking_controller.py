"""CPU exercise of the lazy controller using synthetic Native-shaped state."""
import json
from types import SimpleNamespace

from parking_controller import apply, command


class Actor:
    def __init__(self, x, y, speed):
        self.x, self.y, self.speed = x, y, speed
        self.controls = []

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=self.y),
                               rotation=SimpleNamespace(yaw=0))

    def get_velocity(self):
        return SimpleNamespace(x=self.speed, y=0)

    def apply_control(self, control):
        self.controls.append(control)


class Carla:
    @staticmethod
    def VehicleControl(**fields):
        return fields


def rejected(action, label):
    try:
        action()
    except ValueError:
        return label
    raise AssertionError('Controller negative accepted: ' + label)


def prove():
    outputs = []
    for target in (40, 60):
        approach = Actor(10, -1.75, 0)
        decision = apply(approach, Carla, target, -6.8)
        assert decision['phase'] == 'approach'
        assert approach.controls[-1]['throttle'] > 0
        assert approach.controls[-1]['steer'] < 0
        closing = Actor(target - 4, -6.8, 6)
        decision = apply(closing, Carla, target, -6.8)
        assert decision['phase'] == 'brake_to_park'
        assert closing.controls[-1]['brake'] == 1
        parked = Actor(target, -6.8, 0)
        decision = apply(parked, Carla, target, -6.8)
        assert decision['phase'] == 'brake_to_park'
        assert parked.controls[-1]['throttle'] == 0
        outputs.append({'target_x_m': target, 'approach_steer_left': True,
                        'brake_before_target': True, 'park_hold_brake': True})
    fast = command(10, -1.75, 10, 40, -6.8, approach_speed_mps=4)
    assert fast['brake'] > 0 and fast['throttle'] == 0
    negatives = [rejected(lambda: command(float('nan'), 0, 0, 40, -6.8),
                          'nonfinite-position'),
                 rejected(lambda: command(10, 0, -1, 40, -6.8),
                          'negative-measured-speed'),
                 rejected(lambda: command(10, 0, 0, 40, -6.8,
                                          approach_speed_mps=0),
                          'zero-approach-request')]
    return {'format': 'c150142-parking-controller-cpu-proof-v1',
            'passed': True, 'synthetic_cases': outputs,
            'negative_rejections': negatives,
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False,
            'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
