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
        fallback = json.loads(json.dumps(construction))
        fallback_config = next(file for file in fallback['files'] if file['path'] == 'config.json')
        changed = json.loads(fallback_config['content'])
        changed['walker_spawn_height_adjustment_m'] = 0.15
        fallback_config['content'] = json.dumps(changed, indent=2) + '\n'
        fallback_path = BASE / 'fallbacks' / side / 'construction.json'
        write(fallback_path, fallback)
        fallback_entry = {
            'id': 'fallback1', 'construction': str(fallback_path.relative_to(BASE)),
            'construction_sha256': sha(fallback_path),
            'trigger': {'source': 'original_native_spawn_and_ground_clearance',
                        'metric': 'walker_initial_vertical_clearance_m',
                        'failure_condition': 'original walker spawn collision or clearance below 0.05 m'},
            'changed_knobs': ['walker_spawn_height_adjustment_m: 0.0 to 0.15'],
            'offline': {}, 'compatibility': {}, 'negative': {}, 'saved_processing': {},
        }
        entry = {'case_id': construction['case_id'], 'kind': 'delivery',
                 'construction': str(path.relative_to(BASE)), 'construction_sha256': sha(path),
                 'measurement_contract': 'native/measurement-' + side + '.json',
                 'measurement_procedure': {'entrypoint': 'saved_walking.py',
                                           'output_schema': 'worker-analysis-report-v1'},
                 'fixture_recipe': str((BASE / 'diagnostic' / side / 'recipe.json').relative_to(ROOT)),
                 'candidate_risk': {
                     'status': 'physical',
                     'reason': 'Original walker spawn may collide with the sourced road surface; '
                               'a measured clearance or collision triggers a 0.15 m vertical spawn offset.'},
                 'candidates': [fallback_entry],
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
