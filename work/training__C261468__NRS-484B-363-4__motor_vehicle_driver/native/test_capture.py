"""CPU checks of exact capture plans and live lamp-state source sampling."""

import copy
import json
from pathlib import Path

from capture import check, lamp_sample

HERE = Path(__file__).resolve().parent


class Lamp:
    def __init__(self, actor_id, state):
        self.id = actor_id
        self.type_id = 'traffic.beacon.yellow'
        self.state = state

    def get_state(self):
        return self.state


class Actors:
    def __init__(self, lamps):
        self.lamps = {x.id: x for x in lamps}

    def find(self, actor_id):
        return self.lamps.get(actor_id)


class World:
    def __init__(self, lamps):
        self.actors = Actors(lamps)

    def get_actors(self):
        return self.actors


def rejected(fn, fragment):
    try:
        fn()
    except ValueError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError('Invalid capture source accepted')


def main():
    configs = [json.loads(x.read_text()) for x in sorted((HERE / 'planned-configs').glob('*.json'))]
    assert len(configs) == 13
    for config in configs:
        assert check(config)['case_id'] == config['case_id']
    bad = copy.deepcopy(configs[0])
    bad['requested_context']['school_in_session'] = not bad['requested_context']['school_in_session']
    rejected(lambda: check(bad), 'differs from exact planned case')
    bad = copy.deepcopy(configs[0])
    bad['cameras'][2]['width'] = 640
    rejected(lambda: check(bad), 'Camera source pose or profile invalid')
    survey = {'planned_context': {'beacon_operational': True},
              'beacon': {'yellow_lights': [
                  {'actor_id': 501, 'asset_id': 'traffic.beacon.yellow'},
                  {'actor_id': 502, 'asset_id': 'traffic.beacon.yellow'}]}}
    world = World([Lamp(501, 'Yellow'), Lamp(502, 'Off')])
    sample = lamp_sample(world, survey, 100, 0)
    assert sample['lamp_actor_ids'] == [501, 502]
    assert sample['yellow_lit'] == [True, False]
    world.actors.lamps[501].state = 'Off'
    world.actors.lamps[502].state = 'Yellow'
    assert lamp_sample(world, survey, 101, 1)['yellow_lit'] == [False, True]
    world.actors.lamps[502].state = 'unknown'
    rejected(lambda: lamp_sample(world, survey, 102, 2), 'not interpretable')
    del world.actors.lamps[502]
    rejected(lambda: lamp_sample(world, survey, 103, 3), 'actor changed')
    assert lamp_sample(world, {'planned_context': {'beacon_operational': False}}, 104, 4) is None
    print(json.dumps({'exact_plan_checks': 13, 'lamp_state_samples': 2,
                      'negative_checks': 4, 'carla_contacted': False}, sort_keys=True))


if __name__ == '__main__':
    main()
