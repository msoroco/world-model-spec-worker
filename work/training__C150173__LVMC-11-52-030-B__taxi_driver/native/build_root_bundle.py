"""Materialize a canonical root bundle from selected probe A without changing it."""
import copy
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent


def main():
    selected = json.loads((PACKAGE / 'native-selected/probe_a/construction.json').read_text())
    root = copy.deepcopy(selected)
    cases = [PACKAGE.name + '__' + suffix for suffix in
             ('probe_a', 'probe_b', 'probe_c', 'probe_d',
              'freight_load', 'freight_unload', 'freight_wait')]
    config_file = next(item for item in root['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    config['supported_case_ids'] = cases
    config_file['content'] = json.dumps(config, indent=2) + '\n'
    root['mechanisms'] = {
        'construction_status': 'executable_prospective',
        'road': 'authored one-way OpenDRIVE yellow parking lane and sign proposal',
        'taxi': 'configuration-driven parked actor, exact stop station and source-sealed body samples',
        'passenger_proxy': 'controlled walker request; original passenger purpose requires independent review',
        'light_express_freight': 'controlled cargo actor movement; original commercial classification and freight purpose require independent actor-bound review',
        'cameras': 'four 20 Hz RGB sensors with original Native frame IDs'}
    root['static_checks'] = [
        'yellow_plan.check validates frozen taxi case, camera geometry and 600-frame 20 Hz duration',
        'runner.py --check verifies the authored 600-frame request without CARLA']
    root['termination_rules'] = [
        'stop after exactly 600 source-joined Native ticks and four camera frames per tick',
        'close encoders and restore prior world before releasing ownership',
        'retain failed attempts and do not fabricate completed measurements']
    for item in root['files']:
        target = PACKAGE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (PACKAGE / 'construction.json').write_text(json.dumps(root, indent=2) + '\n')
    return {'files': len(root['files']), 'supported_case_ids': len(cases)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
