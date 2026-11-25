"""Synthetic-only exact exit-construction protocol check; no CARLA capture."""
import argparse
import json
from pathlib import Path

from controlled_access_exit import CASES, build_case


class FixtureAdapter:
    def __init__(self, map_hash):
        self.map_hash = map_hash
        self.calls = []
        self.actors = []

    def read_map_hash(self):
        return self.map_hash

    def read_controlled_access(self, road):
        self.calls.append(('controlled_access', road['map_sha256']))
        return road['controlled_access_readback']

    def read_exit_connection(self, road):
        self.calls.append(('exit_connection', road['map_sha256']))
        return road['exit_connection_readback']

    def spawn_vehicle(self, point, blueprint, role):
        actor = f'{role}_{len(self.actors)}'
        self.actors.append(actor)
        self.calls.append(('spawn', role, tuple(point), blueprint))
        return actor

    def set_route(self, actor, waypoints, role):
        self.calls.append(('route', role, actor, len(waypoints)))

    def set_headway(self, actor, seconds):
        self.calls.append(('headway', actor, seconds))

    def set_exit_policy(self, actor, policy, approaching):
        self.calls.append(('policy', actor, policy, len(approaching)))

    def destroy(self, actor):
        self.calls.append(('destroy', actor))


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    scene = json.loads((root / 'scene.json').read_text())
    if scene.get('source_kind') != 'synthetic_diagnostic_fixture' or scene.get('accepted_original_source') is not False:
        raise ValueError('synthetic provenance required')
    if config['selected_case_id'] != scene['case_id'] or config['rate_hz'] != 20 or config['duration_s'] != 45:
        raise ValueError('exact case or capture contract changed')
    spec = config['case']
    case = next((item for item in CASES if item.name == spec['name']), None)
    if case is None or (case.policy, case.approaching_count, case.approach_headway_s) != (spec['policy'], spec['approaching_count'], spec['approach_headway_s']):
        raise ValueError('case design changed')
    adapter = FixtureAdapter(scene['road']['map_sha256'])
    made = build_case(adapter, scene, case)
    if len(made['approaching']) != case.approaching_count or len(made['owned']) != case.approaching_count + 1:
        raise ValueError('approaching actors not constructed')
    if not any(call[0] == 'policy' and call[2] == case.policy for call in adapter.calls):
        raise ValueError('exit policy not requested')
    if len([call for call in adapter.calls if call[0] == 'route' and call[1] == 'approaching']) != case.approaching_count:
        raise ValueError('approaching route not constructed')
    return scene


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    scene = check()
    if not args.check:
        raise ValueError('synthetic source cannot authorize Native capture')
    print('synthetic exit protocol passed: ' + scene['case_id'])
