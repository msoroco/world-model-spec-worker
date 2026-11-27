"""Small CPU motion test; no CARLA or physical acceptance is implied."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


spec = importlib.util.spec_from_file_location('school_pass_controller', Path(__file__).with_name('controller.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def survey(axis):
    return {'road_axis_xy': list(axis), 'zone_station_bounds_m': [0, 250],
            'ego': {'xyz_m': [10 * axis[0], 10 * axis[1], 0]},
            'other': {'xyz_m': [22 * axis[0], 22 * axis[1], 0]}}


def run_trajectory(axis, side):
    controller = module.PassController(survey(axis), pass_side=side)
    ego = list(survey(axis)['ego']['xyz_m'])
    other = list(survey(axis)['other']['xyz_m'])
    phases, crossings = [], 0
    was_behind = True
    for _ in range(500):
        command = controller.step(ego, other)
        phases.append(command['phase'])
        if was_behind and command['subject_ahead']:
            crossings += 1
            assert command['phase'] == 'abreast'
            assert command['in_signed_zone']
            was_behind = False
        vx, vy = command['ego_velocity_xy_mps']
        ox, oy = command['other_velocity_xy_mps']
        ego[0] += vx * .05
        ego[1] += vy * .05
        other[0] += ox * .05
        other[1] += oy * .05
        if command['phase'] == 'complete':
            break
    assert crossings == 1
    assert phases.index('depart') < phases.index('abreast') < phases.index('return') < phases.index('complete')
    assert abs(command['ego_lateral_m']) <= .35
    assert command['ego_station_m'] < 250
    return command


class FakeActor:
    def __init__(self):
        self.velocity = None

    def set_target_velocity(self, value):
        self.velocity = value


def run():
    for axis in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for side in (-1, 1):
            run_trajectory(axis, side)
    ego, other = FakeActor(), FakeActor()
    carla = SimpleNamespace(Vector3D=lambda **kw: kw)
    module.request_velocities(ego, other, carla, {
        'ego_velocity_xy_mps': (8, 1.5), 'other_velocity_xy_mps': (4, 0)})
    assert ego.velocity == {'x': 8, 'y': 1.5, 'z': 0}
    assert other.velocity == {'x': 4, 'y': 0, 'z': 0}
    rejected = 0
    for change in (
        {'road_axis_xy': [0.5, 0]},
        {'zone_station_bounds_m': [0, 100]},
        {'other': {'xyz_m': [5, 0, 0]}},
        {'other': {'xyz_m': [22, 5, 0]}},
    ):
        plan = survey((1, 0))
        plan.update(change)
        try:
            module.PassController(plan)
        except ValueError:
            rejected += 1
    try:
        module.PassController(survey((1, 0)), pass_side=0)
    except ValueError:
        rejected += 1
    assert rejected == 5
    print('8 axis/side same-direction pass trajectories and lane returns passed')
    print('Two CARLA velocity requests and 5 invalid-survey rejections passed')


if __name__ == '__main__':
    run()
