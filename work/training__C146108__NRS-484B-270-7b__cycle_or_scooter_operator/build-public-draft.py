"""Bind three exact CPU drafts to public compatibility inputs while partial."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASES = ('bicycle_pass_wide', 'electric_bicycle_pass_wide',
         'electric_bicycle_pass_narrow')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    batch = json.loads((REPO / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'status': 'partial_cpu_diagnostic', 'delivery_ready': False,
        'cases': []}
    proposal = {'format': 'worker-cases-proposal', 'cell_id': 'C146108',
        'actor': 'cycle_or_scooter_operator', 'status': 'draft',
        'sweep_specs': [], 'sweeps_expanded': True, 'cases': []}
    for suffix in CASES:
        family = 'draft-bicycle' if suffix.startswith('bicycle') else 'draft-ebike'
        construction_path = HERE / family / suffix / 'primary/construction.json'
        construction = json.loads(construction_path.read_text())
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        manifest['cases'].append({'case_id': construction['case_id'],
            'kind': 'delivery', 'construction': str(construction_path.relative_to(HERE)),
            'construction_sha256': sha(construction_path),
            'measurement_contract': suffix + '-measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': 'work/' + HERE.name + '/diagnostic/' + suffix + '/fixture-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Native rider spawn, complete pass and four-view visibility need original motion review'},
            'candidates': [], 'delivery_readiness': 'incomplete'})
        proposal['cases'].append({'case_id': construction['case_id'],
            'target_law_id': 'NRS-484B-270-7b', 'target_type': 'controlled_attempt',
            'rationale': 'Source-grounded full rider pass of a motor vehicle in the frozen one-way multilane cell',
            'variable_assignments': {'rider_class': config['rider_class'],
                                     'rider_y_m': config.get('rider_y_m', -1.75)},
            'unresolved_judgment_calls': ['No source-backed safe-pass or endangerment threshold',
                'Native physical class, occupants and visible evasive motion require review'],
            'recording_description': construction['recording_description']})
    write(HERE / 'selected-public-draft-manifest.json', manifest)
    write(HERE / 'proposals/cases.json', proposal)
    print(json.dumps({'selected_cases': len(CASES),
                      'manifest_sha256': sha(HERE / 'selected-public-draft-manifest.json')}))


if __name__ == '__main__':
    main()
