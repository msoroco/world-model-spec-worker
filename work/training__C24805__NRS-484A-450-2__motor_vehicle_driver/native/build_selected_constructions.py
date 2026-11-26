"""Adapt the tested no-reference Native pattern to C24805's exact cases.

The source package supplies implementation structure only. This builder binds
C24805's own road, identity, cases, and fresh construction hashes. No proof
receipt is transferred from the source package.
"""

import hashlib
import json
from copy import deepcopy
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SOURCE = ROOT / 'work/training__C111325__NRS-484A-450-2__motor_vehicle_driver'
OLD = 'training__C111325__NRS-484A-450-2__motor_vehicle_driver'
NEW = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, body):
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n')


def adapt(value, old_suffix, new_suffix):
    if isinstance(value, str):
        return (value.replace(OLD, NEW)
                .replace('C111325', 'C24805')
                .replace('c111325', 'c24805')
                .replace('sight_' + old_suffix, new_suffix))
    if isinstance(value, list):
        return [adapt(item, old_suffix, new_suffix) for item in value]
    if isinstance(value, dict):
        return {key: adapt(item, old_suffix, new_suffix)
                for key, item in value.items()}
    return value


def build():
    entries = []
    road = (HERE / 'native/road.xodr').read_text()
    for source_suffix, suffix in (('stop', 'probe_a'), ('pass', 'probe_b')):
        source = SOURCE / f'selected-sight_{source_suffix}-primary-construction.json'
        body = adapt(json.loads(source.read_text()), source_suffix, suffix)
        body['case_id'] = NEW + '__' + suffix
        body['cell_id'] = 'C24805'
        body['status'] = 'selected_cpu_construction_pending_proofs'
        body['source_adaptation'] = {
            'pattern': 'NRS-484A-450-2 no-reference Native runner',
            'source_sha256': sha(source),
            'proofs_reused': False,
        }
        files = {item['path']: item['content'] for item in body['files']}
        files['authored-road.xodr'] = road
        config = json.loads(files['config.json'])
        config['case_id'] = body['case_id']
        config['selected_case_id'] = body['case_id']
        config['cell_id'] = 'C24805'
        config['case']['case_id'] = body['case_id']
        config['supported_case_ids'] = [NEW + '__probe_a', NEW + '__probe_b']
        files['config.json'] = json.dumps(config, indent=2) + '\n'
        body['files'] = [{'path': name, 'content': content}
                         for name, content in sorted(files.items())]
        target = HERE / f'selected-{suffix}-primary-construction.json'
        write(target, body)
        fallback = deepcopy(body)
        for item in fallback['files']:
            if item['path'] == 'live_capture.py':
                old = 'START_Y = -50.0'
                if old not in item['content']:
                    raise ValueError('Native spawn-position fallback source absent')
                item['content'] = item['content'].replace(old, 'START_Y = -55.0')
        fallback_target = HERE / f'selected-{suffix}-fallback1-construction.json'
        write(fallback_target, fallback)
        entries.append({
            'case_id': body['case_id'],
            'kind': 'delivery',
            'construction': target.name,
            'construction_sha256': sha(target),
            'fixture_recipe': f'work/{NEW}/selected-{suffix}-fixture-recipe.json',
            'measurement_contract': f'selected-{suffix}-measurement-contract.json',
            'candidate_risk': {
                'status': 'physical',
                'reason': 'Native braking and occlusion can shift first view opening and halt',
            },
            'candidates': [{
                'id': 'fallback1',
                'construction': fallback_target.name,
                'construction_sha256': sha(fallback_target),
                'changed_knobs': ['move subject spawn 5 m farther from view opening'],
                'trigger': {'source': 'sight_samples.jsonl',
                            'metric': 'first_view_open_frame',
                            'failure_condition': 'view opens before full halt window'},
            }],
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
        })
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': NEW,
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'selected_cpu_construction_pending_proofs',
        'cases': entries,
    }
    target = HERE / 'selected-construction-manifest.json'
    write(target, manifest)
    return {'cases': len(entries), 'manifest_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
