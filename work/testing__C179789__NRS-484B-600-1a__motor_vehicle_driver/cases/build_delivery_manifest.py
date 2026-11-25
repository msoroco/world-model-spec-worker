"""Bind the eight exact offline constructions into a draft delivery selection."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    index = json.loads((ROOT / 'cases/condition-offline-index.json').read_text())
    cases = []
    for row in index['cases']:
        suffix = row['case_id'].split('__')[-1]
        recipe = ROOT / ('fixture-recipe.json' if suffix == 'dry_open_traffic'
                         else 'cases/' + suffix + '-fixture-recipe.json')
        cases.append({
            'case_id': row['case_id'], 'kind': 'delivery',
            'construction': row['construction'],
            'construction_sha256': row['construction_sha256'],
            'offline': {'command': row['command'], 'exit_code': row['exit_code'],
                        'construction_sha256': row['construction_sha256'],
                        'log': row['log'], 'log_sha256': row['log_sha256']},
            'measurement_procedure': {'entrypoint': 'finalizer.py'},
            'measurement_contract': 'measurement-contract.json',
            'fixture_recipe': recipe.relative_to(REPO).as_posix(),
            'physical_preparation': {
                'receipt': 'cases/' + row['case_id'].split('__')[-1] + '-physical-preparation.json',
                'sha256': sha(ROOT / 'cases' / (row['case_id'].split('__')[-1] + '-physical-preparation.json'))},
            'candidate_risk': {'status': 'physical',
                               'reason': 'Native road condition, lead gap and camera coverage require review.'},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        })
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': cases, 'draft': True}
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'draft': True}))


if __name__ == '__main__':
    build()
