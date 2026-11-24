"""CPU mock proof of exact turn-signal setup and camera cleanup."""
import hashlib
import json
from pathlib import Path

from signal_distance import measure
from turn_capture_plan import BLUEPRINT, CAMERAS, plan, setup


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Blueprint:
    def __init__(self, name):
        self.id = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Library:
    def find(self, name):
        return Blueprint(name)


class Actor:
    def __init__(self, name):
        self.type_id = name
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.actors = []

    def get_blueprint_library(self):
        return Library()

    def spawn_actor(self, bp, transform, attach_to=None):
        if self.fail_at == len(self.actors):
            raise RuntimeError('synthetic camera spawn failure')
        actor = Actor(bp.id)
        self.actors.append(actor)
        return actor


class Carla:
    @staticmethod
    def Location(**kwargs):
        return kwargs

    @staticmethod
    def Transform(location):
        return location


def survey(request):
    return {'median_opening_verified': True, 'incoming_lane_verified': True,
            'turn_route_verified': True, 'district_class': request['district_class'],
            'weather': request['weather']}


def main():
    assignment = Path(__file__).resolve().parents[1]
    comparisons = []
    for condition in ('other_long', 'other_short', 'district_long', 'district_short'):
        request = plan(condition)
        source = assignment/'native/diagnostic-sources'/condition
        metric = measure(source)
        world = World()
        built = setup(world, Carla, request, survey(request))
        if (built.ego.type_id != BLUEPRINT or len(built.cameras) != 4 or
                len(world.actors) != 1+len(CAMERAS) or
                metric['continuous_signal_distance_m'] !=
                request['requested_signal_distance_m']):
            raise ValueError('Source/request or camera setup differs')
        comparisons.append({'condition': condition,
            'source_index_sha256': metric['source_index_sha256'],
            'requested_and_measured_signal_distance_m':
                metric['continuous_signal_distance_m'],
            'camera_names': sorted(built.cameras)})
    a, b, c, d = [plan(x) for x in ('other_long','other_short',
                                    'district_long','district_short')]
    for left, right in ((a,b),(c,d)):
        fixed = set(left)-{'condition','requested_signal_distance_m'}
        if any(left[key] != right[key] for key in fixed):
            raise ValueError('Comparison changed fixed Native setup')
    request = plan('other_long')
    try:
        setup(World(), Carla, request, {})
    except ValueError as exc:
        if 'survey missing' not in str(exc):
            raise
    else:
        raise ValueError('Missing Native survey accepted')
    failed = World(fail_at=3)
    try:
        setup(failed, Carla, request, survey(request))
    except RuntimeError:
        pass
    else:
        raise ValueError('Synthetic partial spawn did not fail')
    if len(failed.actors) != 3 or not all(actor.destroyed for actor in failed.actors):
        raise ValueError('Partial spawn left actors owned')
    receipt = {'format': 'c124163-native-turn-setup-cpu-v1',
        'passed': True, 'conditions': comparisons,
        'camera_specs': [list(x) for x in CAMERAS],
        'missing_survey_rejected': True, 'partial_spawn_cleaned': True,
        'setup_sha256': sha(assignment/'native/turn_capture_plan.py'),
        'original_native_observed': False,
        'visible_signal_pixels_verified': False,
        'legal_verdict_claimed': False}
    output = assignment/'native/turn-setup-proof.json'
    output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'passed':True,'conditions':4,'camera_streams':4,
                      'proof_sha256':sha(output)}))


if __name__ == '__main__':
    main()
