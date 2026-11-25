"""Synthetic-only passenger curb protocol check; never authorizes Native capture."""
import argparse
import json
from pathlib import Path

from passenger_zone import CASES, build_case


class FixtureAdapter:
    def __init__(self):
        self.calls = []
        self.actors = []

    def spawn_vehicle(self, point, blueprint, role):
        actor = 'vehicle_' + str(len(self.actors))
        self.actors.append(actor)
        self.calls.append(('spawn_vehicle', point, blueprint, role))
        return actor

    def spawn_passenger(self, point, blueprint):
        actor = 'passenger_' + str(len(self.actors))
        self.actors.append(actor)
        self.calls.append(('spawn_passenger', point, blueprint))
        return actor

    def set_route(self, ego, route, pose):
        self.calls.append(('route', ego, route, pose))

    def set_conduct(self, ego, conduct):
        self.calls.append(('conduct', ego, conduct))

    def set_passenger_action(self, passenger, ego, action, release_delay_s):
        self.calls.append(('passenger_action', passenger, ego, action, release_delay_s))

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
    if case is None or (case.conduct, case.passenger_action, case.release_delay_s, case.hours) != (
            spec['conduct'], spec['passenger_action'], spec['release_delay_s'], spec['hours']):
        raise ValueError('case design changed')
    adapter = FixtureAdapter()
    made = build_case(adapter, scene, case)
    if len(made['owned']) != 2 or not any(call[0] == 'passenger_action' and call[3] == case.passenger_action for call in adapter.calls):
        raise ValueError('passenger action protocol absent')
    return scene


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    scene = check()
    if not args.check:
        raise ValueError('synthetic source cannot authorize Native capture')
    print('synthetic passenger zone protocol passed: ' + scene['case_id'])
