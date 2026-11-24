"""CPU fake-world wiring proof for the Native setup API."""
import argparse
import hashlib
import json
from pathlib import Path

from bicycle_setup import BLUEPRINT, plan, setup


class Blueprint:
    def __init__(self, identifier):
        self.id = identifier
        self.attrs = {}

    def set_attribute(self, key, value):
        self.attrs[key] = value


class Library:
    def find(self, identifier):
        return Blueprint(identifier)


class Actor:
    def __init__(self, identifier):
        self.type_id = identifier
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, fail_at=None):
        self.actors = []
        self.fail_at = fail_at

    def get_blueprint_library(self):
        return Library()

    def spawn_actor(self, bp, transform, attach_to=None):
        if self.fail_at == len(self.actors):
            raise RuntimeError('synthetic spawn failure')
        actor = Actor(bp.id)
        self.actors.append(actor)
        return actor


class Carla:
    class Location:
        def __init__(self, **kwargs):
            self.xyz = kwargs

    class Rotation:
        def __init__(self, **kwargs):
            self.yaw = kwargs

    class Transform:
        def __init__(self, location, rotation=None):
            self.location = location
            self.rotation = rotation


SURVEY = {'route_lane_verified': True, 'stop_sign_governs_route': True,
          'approach_clearance_verified': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    args = parser.parse_args()
    requests = [plan(c) for c in ('condition_a', 'condition_b')]
    assert requests[0]['requested_peak_speed_mps'] == 3.0
    assert requests[1]['requested_peak_speed_mps'] == 5.0
    assert {key for key in requests[0] if requests[0][key] != requests[1][key]} == {
        'condition', 'requested_peak_speed_mps'}
    assert all({c['name'] for c in r['cameras']} == set(r['source_streams']) ==
               {'overview', 'approach', 'reference_corner', 'driver_reference'}
               for r in requests)
    for request in requests:
        world = World()
        built = setup(world, Carla, request, SURVEY)
        assert built.bicycle.type_id == BLUEPRINT
        assert len(world.actors) == 5 and len(built.cameras) == 4
    try:
        setup(World(), Carla, requests[0], {})
    except ValueError as exc:
        assert 'survey missing' in str(exc)
    else:
        raise AssertionError('missing Native survey accepted')
    world = World(fail_at=3)
    try:
        setup(world, Carla, requests[0], SURVEY)
    except RuntimeError as exc:
        assert 'spawn failure' in str(exc)
    else:
        raise AssertionError('sensor failure accepted')
    assert len(world.actors) == 3 and all(a.destroyed for a in world.actors)
    result = {
        'format': 'c111325-native-bicycle-setup-cpu-proof-v1', 'passed': True,
        'setup_sha256': hashlib.sha256(Path(__file__).with_name('bicycle_setup.py').read_bytes()).hexdigest(),
        'conditions': [r['condition'] for r in requests], 'frames': 600,
        'rate_hz': 20, 'source_cameras': list(requests[0]['source_streams']),
        'negative_missing_survey_rejected': True,
        'negative_partial_spawn_cleanup': True,
        'comparison_variable_isolated': True,
        'carla_execution_observed': False, 'prudence_verdict_claimed': False,
    }
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'conditions': 2, 'cameras': 4,
                      'negative_cases': 2}))


if __name__ == '__main__':
    main()
