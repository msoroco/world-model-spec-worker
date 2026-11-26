"""Exact exit construction check and source-gated original CARLA capture."""
import argparse
import json
import os
import shutil
from pathlib import Path

from controlled_access_exit import CASES, build_case
from reviewed_site import verify


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


def validate_config():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    cameras = config.get('cameras')
    if config['rate_hz'] != 20 or config['duration_s'] != 45 or \
            [(c.get('name'), c.get('width'), c.get('height')) for c in cameras] != [
                ('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]:
        raise ValueError('exact case or capture contract changed')
    spec = config['case']
    case = next((item for item in CASES if item.name == spec['name']), None)
    if case is None or (case.policy, case.approaching_count, case.approach_headway_s) != (spec['policy'], spec['approaching_count'], spec['approach_headway_s']):
        raise ValueError('case design changed')
    if spec.get('ego_start_variant') not in ('primary', 'fallback1'):
        raise ValueError('exact reviewed-route ego start variant missing')
    if not config['selected_case_id'].endswith('__' + case.name):
        raise ValueError('exact case identity changed')
    return config, case


def check():
    config, case = validate_config()
    scene = json.loads((Path(__file__).resolve().parent / 'scene.json').read_text())
    if scene.get('source_kind') != 'synthetic_diagnostic_fixture' or scene.get('accepted_original_source') is not False:
        raise ValueError('synthetic provenance required')
    if config['selected_case_id'] != scene['case_id']:
        raise ValueError('exact diagnostic case changed')
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
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        scene = check()
        print('synthetic exit protocol passed: ' + scene['case_id'])
    else:
        if not args.output_dir:
            raise ValueError('Native output directory required')
        source = os.environ.get('C228302_REVIEWED_SITE_PACKET')
        if not source:
            raise ValueError('reviewed original exit site packet path required')
        config, case = validate_config()
        reviewed = verify(Path(source), case)
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        archive = output / 'reviewed-site-packet'
        archive.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, archive / 'packet.json')
        for item in reviewed['packet']['source_bindings'].values():
            destination = archive / item['path']
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source).parent / item['path'], destination)
        from native_original import run, finalize
        capture = run(config, case, Path(source), output, args.host, args.port)
        finalize(config, case, output, capture)
