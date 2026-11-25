"""CPU mock proof of readback-driven bicycle control and negative paths."""
import argparse
import hashlib
import json
from pathlib import Path
from bicycle_control import apply, command


class Vec:
    def __init__(self, x=0.0, y=0.0):
        self.x, self.y = x, y


class Transform:
    def __init__(self, x, y=0.0):
        self.location = Vec(x, y)


class Bicycle:
    type_id = 'vehicle.bh.crossbike'
    id = 71

    def __init__(self, x, velocity=0.0, y=-1.75):
        self.transform = Transform(x, y)
        self.velocity = Vec(velocity)
        self.control = None

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return self.velocity

    def apply_control(self, value):
        self.control = value


class Carla:
    class VehicleControl:
        def __init__(self, throttle, brake, steer):
            self.throttle, self.brake, self.steer = throttle, brake, steer


def rejects(call, message):
    try:
        call()
    except ValueError as exc:
        if message not in str(exc):
            raise AssertionError(str(exc)) from exc
    else:
        raise AssertionError('Incorrect source was accepted: ' + message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    args = parser.parse_args()
    slow = apply(Bicycle(-40, 0), Carla, 'condition_a')
    fast = apply(Bicycle(-40, 0), Carla, 'condition_b')
    assert slow['target_speed_mps'] == 3.0
    assert fast['target_speed_mps'] == 5.0
    assert slow['throttle'] < fast['throttle']
    assert slow['source_kind'] == fast['source_kind'] == 'original_native_actor_readback'
    near = apply(Bicycle(-2.08, 1.0), Carla, 'condition_b')
    assert near['throttle'] == 0 and near['brake'] == 1
    rejects(lambda: command('condition_b', -1.7, 2.0), 'crossed')
    rejects(lambda: command('condition_a', float('nan'), 0.0), 'Invalid Native position')
    rejects(lambda: command('condition_a', -40, 0, {'position_x_m': -39}), 'reversed')
    rejects(lambda: apply(Bicycle(-40, 0, 1.0), Carla, 'condition_a'), 'departed')
    wrong = Bicycle(-40)
    wrong.type_id = 'vehicle.tesla.model3'
    rejects(lambda: apply(wrong, Carla, 'condition_a'), 'not the selected bicycle')
    result = {'format': 'c111325-bicycle-controller-cpu-proof-v1',
              'passed': True, 'controller_sha256': hashlib.sha256(
                  Path(__file__).with_name('bicycle_control.py').read_bytes()).hexdigest(),
              'conditions': ['condition_a', 'condition_b'],
              'source': 'mock Native actor readbacks', 'negative_checks': 5,
              'original_native_executed': False,
              'reasonable_and_prudent_verdict': None}
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'conditions': 2, 'negative_checks': 5}))


if __name__ == '__main__':
    main()
