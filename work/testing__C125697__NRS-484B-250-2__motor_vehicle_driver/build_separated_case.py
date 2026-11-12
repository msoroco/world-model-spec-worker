"""Build the selected Off-state separated-entry construction at the same site."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEFT = HERE.name+'__off_ego_left_near_time'
SEPARATED = HERE.name+'__off_ego_left_separated'
OUT = HERE/'cases/off_ego_left_separated'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if any(row['case_id'] == SEPARATED for row in manifest['cases']):
        raise ValueError('Separated construction already selected; retain exact proofs')
    bundle = copy.deepcopy(json.loads((HERE/'construction.json').read_text()))
    bundle['case_id'] = SEPARATED
    bundle['status'] = 'synthetic_diagnostic_only'
    for item in bundle['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = SEPARATED
            config['other_release_frame'] = 60
            item['content'] = json.dumps(config, indent=2, allow_nan=False)+'\n'
            item.pop('source', None)
        elif item['path'] in ('runner.py', 'finalizer.py'):
            item['content'] = item['content'].replace(LEFT, SEPARATED)
            item.pop('source', None)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT/'construction.json'
    path.write_text(json.dumps(bundle, indent=2, allow_nan=False)+'\n')
    manifest['cases'].append({
        'case_id': SEPARATED, 'kind': 'delivery',
        'construction': str(path.relative_to(HERE)),
        'construction_sha256': sha(path),
        'measurement_procedure': {'entrypoint': 'finalizer.py'},
        'measurement_contract': str((OUT/'measurement-contract.json').relative_to(HERE)),
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        'candidate_risk': {'status': 'physical',
                           'reason': 'Traffic or braking can compress the intended separated entry times.'},
    })
    manifest['status'] = 'partial_three_case_construction'
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'case_id': SEPARATED, 'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
