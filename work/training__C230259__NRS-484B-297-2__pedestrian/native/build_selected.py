"""Materialize the two exact draft bundles as selected, still partial proposals."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    draft = json.loads((BASE / 'draft-native-manifest.json').read_text())
    entries = []
    for index, side in enumerate('ab'):
        construction = json.loads((BASE / 'draft-native' / side / 'construction.json').read_text())
        construction['status'] = 'selected_cpu_preparation'
        path = BASE / ('construction.json' if side == 'a' else 'cases/condition_b/construction.json')
        write(path, construction)
        if side == 'a':
            for file in construction['files']:
                target = BASE / file['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(file['content'])
        entry = {'case_id': construction['case_id'], 'kind': 'delivery',
                 'construction': str(path.relative_to(BASE)), 'construction_sha256': sha(path),
                 'measurement_contract': 'native/measurement-' + side + '.json',
                 'measurement_procedure': {'entrypoint': 'saved_walking.py',
                                           'output_schema': 'worker-analysis-report-v1'},
                 'fixture_recipe': str((BASE / 'diagnostic' / side / 'recipe.json').relative_to(ROOT)),
                 'candidate_risk': draft['cases'][index]['candidate_risk'], 'candidates': [],
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                 'offline': {}, 'compatibility': {}, 'negative': {},
                 'physical_preparation': {}, 'acquisition': {}, 'delivery_acceptance': {},
                 'post_capture': {}}
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': BASE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'partial_selected_proof_work', 'delivery_ready': False,
                'original_native_observed': False, 'cases': entries}
    write(BASE / 'execution-manifest.json', manifest)
    print(json.dumps({'case_ids': [e['case_id'] for e in entries],
                      'construction_hashes': [e['construction_sha256'] for e in entries]}))


if __name__ == '__main__':
    main()
