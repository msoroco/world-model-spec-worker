"""CPU test the local CARLA control call shape and exact stop-policy split."""
import json
from types import SimpleNamespace

from live_capture import FRAMES, CASES, control, requested_speed


class FakeCarla:
    @staticmethod
    def VehicleControl(**kwargs):
        return kwargs


class FakeEgo:
    def __init__(self, speed):
        self.speed = speed

    def get_velocity(self):
        return SimpleNamespace(x=0, y=self.speed, z=0)

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=1.75),
                               rotation=SimpleNamespace(yaw=90))


def prove():
    assert requested_speed(120, CASES['full_stop']) == 0
    assert requested_speed(120, CASES['rolling']) == 2
    assert requested_speed(0, CASES['full_stop']) == 8
    assert requested_speed(FRAMES - 1, CASES['rolling']) == 8
    hard = control(FakeCarla, FakeEgo(8), 0)
    rolling = control(FakeCarla, FakeEgo(2.5), 2)
    if hard['brake'] != 1 or hard['throttle'] != 0 or not 0 <= rolling['brake'] < 1:
        raise AssertionError('Full stop and rolling control requests differ incorrectly')
    rejected = 0
    for frame, case in ((-1, CASES['full_stop']), (FRAMES, CASES['rolling']),
                        (100, 'foreign_case')):
        try:
            requested_speed(frame, case)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError('Invalid frame/case request accepted')
    return {'format': 'c295180-controller-cpu-proof-v1', 'hard_stop_control': hard,
            'rolling_control': rolling, 'invalid_request_rejections': rejected,
            'native_executed': False, 'physical_completion_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2, sort_keys=True))
