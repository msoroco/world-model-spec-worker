"""CPU proof of exact capture plan and original-source readback branches."""
from dataclasses import dataclass

from nonthrough_native_capture import check, original_control_state, original_viewpoint_rays
from nonthrough_scene import request


@dataclass
class Point:
    x: float
    y: float
    z: float


@dataclass
class Rotation:
    yaw: float


@dataclass
class Pose:
    location: Point
    rotation: Rotation


class Carla:
    Location = Point


class Hit:
    location = Point(-1, -4, 1)
    label = 'Buildings'


class World:
    def cast_ray(self, start, end):
        if start.z != 1.5 or end.z != 1.5:
            raise AssertionError('Wrong observer height')
        return [Hit()]


class Actor:
    id = 17
    is_alive = True

    def get_transform(self):
        return Pose(Point(-3, -5, .5), Rotation(0))


class Signal(Actor):
    id = 19

    def get_state(self):
        return 'Green'


class NoRays:
    pass


def rejects(fn, fragment):
    try:
        fn()
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(str(exc)) from exc
    else:
        raise AssertionError('Missing original source was accepted')


def main():
    summary = check()
    assert summary['exact_case_count'] == 10 and not summary['carla_imported']
    assert all(row['frames'] == 600 for row in summary['cases'])
    rays = original_viewpoint_rays(World(), Carla(), 71, 3.5)
    assert rays['native_frame'] == 71 and len(rays['rays']) == 18
    assert rays['nearest_legal_viewpoint_unassessed']
    rejects(lambda: original_viewpoint_rays(NoRays(), Carla(), 71, 3.5), 'cast_ray')
    police = original_control_state({'officer': Actor()}, request('police_control', exception='police'), 71, 3.5)
    assert police['officer']['actor_id'] == 17 and police['officer_direction_legally_unassessed']
    rejects(lambda: original_control_state({'officer': None}, request('police_control', exception='police'), 71, 3.5),
            'officer actor unavailable')
    signal = original_control_state({'signal': Signal()}, request('signal_control', exception='signal'), 71, 3.5)
    assert signal['signal']['state'] == 'Green' and signal['signal_controls_approach_legally_unassessed']
    rejects(lambda: original_control_state({'signal': None}, request('signal_control', exception='signal'), 71, 3.5),
            'signal actor/state unavailable')
    print('ten exact capture plans and original viewpoint/officer/signal readback CPU paths pass; missing-source negatives reject')


if __name__ == '__main__':
    main()
